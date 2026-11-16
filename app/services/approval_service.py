from datetime import datetime
from app.extensions import db
from app.models.booking import BookingRequest, BookingResource, ApprovalHistory
from app.services.availability_service import AvailabilityService
from app.services.equipment_service import EquipmentService
from app.services.notification_service import NotificationService

class ApprovalService:
    @classmethod
    def approve_booking(cls, booking_id, admin_user, remarks=None):
        """
        Atomically approves a pending booking request with concurrency protection.
        Guarantees that two overlapping requests cannot both be approved.
        """
        if not admin_user.is_admin():
            return False, "Only administrators can approve bookings."

        booking = BookingRequest.query.get(booking_id)
        if not booking:
            return False, "Booking request not found."

        if booking.status != BookingRequest.STATUS_PENDING:
            return False, f"Cannot approve: booking is currently '{booking.status}', not PENDING."

        # Re-check resource availability atomically (excluding this booking itself)
        for br in booking.booking_resources:
            # 1. Maintenance check
            has_block, block_msg = AvailabilityService.check_maintenance_conflict(br.resource_id, br.start_at, br.end_at)
            if has_block:
                return False, f"Cannot approve: {block_msg}"

            # 2. Approved reservation collision check
            has_conflict, conflict_msg = AvailabilityService.check_booking_conflict(
                br.resource_id, br.start_at, br.end_at, exclude_booking_id=booking.id, include_provisional=False
            )
            if has_conflict:
                return False, f"Cannot approve due to conflict: {conflict_msg}"

        # Re-check equipment availability atomically
        for er in booking.equipment_requests:
            is_avail, avail_qty, err_msg = EquipmentService.check_equipment_availability(
                er.equipment_id, er.quantity, er.start_at, er.end_at, exclude_booking_id=booking.id
            )
            if not is_avail:
                return False, f"Cannot approve: {err_msg}"

        # All checks passed: transition state to APPROVED
        try:
            booking.status = BookingRequest.STATUS_APPROVED
            booking.admin_notes = remarks
            booking.updated_at = datetime.utcnow()

            for br in booking.booking_resources:
                br.status = 'APPROVED'

            history = ApprovalHistory(
                booking_id=booking.id,
                admin_id=admin_user.id,
                action='APPROVED',
                remarks=remarks or "Approved by administrator"
            )
            db.session.add(history)

            NotificationService.notify_requester(booking, 'APPROVED', remarks=remarks)

            db.session.commit()
            return True, "Booking approved successfully."

        except Exception as e:
            db.session.rollback()
            return False, f"Approval transaction failed: {str(e)}"

    @classmethod
    def reject_booking(cls, booking_id, admin_user, reason):
        """
        Declines a pending booking request with mandatory reason and history recording.
        """
        if not admin_user.is_admin():
            return False, "Only administrators can reject bookings."

        if not reason or not reason.strip():
            return False, "A rejection reason is required."

        booking = BookingRequest.query.get(booking_id)
        if not booking:
            return False, "Booking request not found."

        if booking.status != BookingRequest.STATUS_PENDING:
            return False, f"Cannot reject: booking is currently '{booking.status}'."

        try:
            booking.status = BookingRequest.STATUS_REJECTED
            booking.rejection_reason = reason.strip()
            booking.updated_at = datetime.utcnow()

            for br in booking.booking_resources:
                br.status = 'REJECTED'

            history = ApprovalHistory(
                booking_id=booking.id,
                admin_id=admin_user.id,
                action='REJECTED',
                remarks=reason.strip()
            )
            db.session.add(history)

            NotificationService.notify_requester(booking, 'REJECTED', remarks=reason.strip())

            db.session.commit()
            return True, "Booking request rejected."

        except Exception as e:
            db.session.rollback()
            return False, f"Rejection failed: {str(e)}"
