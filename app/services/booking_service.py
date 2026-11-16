from datetime import datetime, date, timedelta
from app.extensions import db
from app.models.event import Event
from app.models.booking import BookingRequest, BookingResource, ApprovalHistory, SystemSetting
from app.models.resource import Resource
from app.models.equipment import Equipment, EquipmentRequest
from app.services.availability_service import AvailabilityService
from app.services.equipment_service import EquipmentService
from app.services.notification_service import NotificationService

class BookingService:
    @classmethod
    def validate_advance_notice(cls, event_date):
        """
        Validates booking date against college advance notice and same-day policies.
        """
        today = date.today()
        if event_date < today:
            return False, "Cannot book events for past dates."

        allow_same_day = SystemSetting.get_value('ALLOW_SAME_DAY_BOOKING', 'true').lower() == 'true'
        if event_date == today and not allow_same_day:
            return False, "Same-day bookings are not permitted by college policy. Please book at least 1 day in advance."

        max_days_str = SystemSetting.get_value('MAX_ADVANCE_BOOKING_DAYS', '60')
        try:
            max_days = int(max_days_str)
        except ValueError:
            max_days = 60

        if (event_date - today).days > max_days:
            return False, f"Bookings can be made at most {max_days} days in advance."

        return True, ""

    @classmethod
    def create_event_booking(cls, requester, event_data, resource_slots, equipment_items=None):
        """
        Atomically creates an Event, BookingRequest, and associated Resource & Equipment allocations.

        :param requester: User object submitting request
        :param event_data: dict with title, description, category, expected_attendance, event_date, start_time, end_time, department_id, society_id, requirements
        :param resource_slots: list of dicts [{'resource_id': int, 'start_at': datetime, 'end_at': datetime}]
        :param equipment_items: list of dicts [{'equipment_id': int, 'quantity': int, 'start_at': datetime, 'end_at': datetime}]
        :return: (success: bool, result_or_error: Union[BookingRequest, str])
        """
        if not requester or not requester.is_active:
            return False, "User account is inactive or invalid."

        # 1. Validate advance notice
        is_valid_date, err = cls.validate_advance_notice(event_data['event_date'])
        if not is_valid_date:
            return False, err

        if not resource_slots:
            return False, "Please select at least one infrastructure resource to book."

        # 2. Validate Resource Slots
        expected_attendance = int(event_data.get('expected_attendance', 1))
        for slot in resource_slots:
            res_id = slot['resource_id']
            s_dt = slot['start_at']
            e_dt = slot['end_at']

            res = Resource.query.get(res_id)
            if not res:
                return False, f"Resource ID {res_id} does not exist."

            # Check capacity policy
            if expected_attendance > res.capacity * 1.5:  # allow 50% overflow buffer before hard blocking
                return False, f"Expected attendance ({expected_attendance}) severely exceeds {res.name} capacity ({res.capacity})."

            # Check availability
            avail, reason = AvailabilityService.is_resource_available(res_id, s_dt, e_dt)
            if not avail:
                return False, f"Cannot reserve {res.name}: {reason}"

        # 3. Validate Equipment Items
        if equipment_items:
            for eq_req in equipment_items:
                eq_id = eq_req['equipment_id']
                qty = int(eq_req['quantity'])
                s_dt = eq_req['start_at']
                e_dt = eq_req['end_at']

                is_avail, avail_qty, err_msg = EquipmentService.check_equipment_availability(eq_id, qty, s_dt, e_dt)
                if not is_avail:
                    return False, f"Equipment error: {err_msg}"

        # 4. Atomic Database Transaction
        try:
            event = Event(
                title=event_data['title'],
                description=event_data['description'],
                category=event_data['category'],
                organiser_id=requester.id,
                department_id=event_data.get('department_id'),
                society_id=event_data.get('society_id'),
                expected_attendance=expected_attendance,
                event_date=event_data['event_date'],
                start_time=event_data['start_time'],
                end_time=event_data['end_time'],
                requirements=event_data.get('requirements')
            )
            db.session.add(event)
            db.session.flush()  # generate event.id

            booking = BookingRequest(
                event_id=event.id,
                requester_id=requester.id,
                status=BookingRequest.STATUS_PENDING
            )
            db.session.add(booking)
            db.session.flush()  # generate booking.id

            for slot in resource_slots:
                br = BookingResource(
                    booking_id=booking.id,
                    resource_id=slot['resource_id'],
                    start_at=slot['start_at'],
                    end_at=slot['end_at'],
                    status='PENDING'
                )
                db.session.add(br)

            if equipment_items:
                for eq_req in equipment_items:
                    er = EquipmentRequest(
                        booking_id=booking.id,
                        equipment_id=eq_req['equipment_id'],
                        quantity=int(eq_req['quantity']),
                        start_at=eq_req['start_at'],
                        end_at=eq_req['end_at']
                    )
                    db.session.add(er)

            # Notify administrators
            NotificationService.notify_admins(
                title="New Booking Request Pending Approval",
                message=f"{requester.name} submitted a booking request for '{event.title}' on {event.event_date}.",
                link=f"/admin/bookings/{booking.id}"
            )

            # In-app notification for requester
            NotificationService.create_notification(
                user_id=requester.id,
                title="Booking Request Submitted",
                message=f"Your booking request for '{event.title}' was submitted successfully and is awaiting administrator approval.",
                link=f"/bookings/{booking.id}"
            )

            db.session.commit()
            return True, booking

        except Exception as e:
            db.session.rollback()
            return False, f"Database transaction failed: {str(e)}"

    @classmethod
    def cancel_booking(cls, booking_id, user, reason):
        """
        Cancels a booking (by the requester or an administrator).
        Releases reserved resources and equipment.
        """
        booking = BookingRequest.query.get(booking_id)
        if not booking:
            return False, "Booking not found."

        if not user.is_admin() and booking.requester_id != user.id:
            return False, "You do not have permission to cancel this booking."

        if booking.status in (BookingRequest.STATUS_CANCELLED, BookingRequest.STATUS_REJECTED):
            return False, f"Booking is already {booking.status.lower()}."

        try:
            booking.status = BookingRequest.STATUS_CANCELLED
            booking.cancellation_reason = reason
            booking.updated_at = datetime.utcnow()

            for br in booking.booking_resources:
                br.status = 'CANCELLED'

            # Record in approval history
            history = ApprovalHistory(
                booking_id=booking.id,
                admin_id=user.id,
                action='CANCELLED',
                remarks=f"Cancelled by {user.role} ({user.name}). Reason: {reason}"
            )
            db.session.add(history)

            # Notifications
            if user.is_admin():
                NotificationService.notify_requester(booking, 'CANCELLED', remarks=reason)
            else:
                NotificationService.notify_admins(
                    title="Booking Cancelled by Requester",
                    message=f"{user.name} cancelled their booking for '{booking.event.title}'. Reason: {reason}",
                    link=f"/admin/bookings/{booking.id}"
                )

            db.session.commit()
            return True, "Booking cancelled successfully."
        except Exception as e:
            db.session.rollback()
            return False, f"Cancellation failed: {str(e)}"
