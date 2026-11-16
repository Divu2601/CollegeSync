from datetime import datetime, time, date, timedelta
from sqlalchemy import and_, or_
from app.extensions import db
from app.models.resource import Resource, ResourceBlock
from app.models.booking import BookingRequest, BookingResource, SystemSetting

class AvailabilityService:
    @staticmethod
    def parse_time_str(time_str):
        """Converts 'HH:MM' string to datetime.time object."""
        if not time_str:
            return None
        parts = [int(p) for p in time_str.split(':')]
        return time(parts[0], parts[1])

    @classmethod
    def check_operating_hours(cls, resource, start_dt, end_dt):
        """
        Validates if [start_dt, end_dt] falls strictly within resource operating hours.
        Returns (is_valid, error_message).
        """
        op_start = cls.parse_time_str(resource.operating_hours_start) or time(9, 0)
        op_end = cls.parse_time_str(resource.operating_hours_end) or time(17, 0)

        # Start and end times on respective days
        start_time = start_dt.time()
        end_time = end_dt.time()

        if start_dt.date() != end_dt.date():
            return False, "Bookings spanning across multiple calendar days are not allowed. Please split into daily bookings."

        if start_time < op_start or end_time > op_end:
            return False, (
                f"Booking interval {start_time.strftime('%H:%M')} - {end_time.strftime('%H:%M')} "
                f"is outside operating hours ({op_start.strftime('%H:%M')} - {op_end.strftime('%H:%M')}) for {resource.name}."
            )

        return True, ""

    @classmethod
    def check_maintenance_conflict(cls, resource_id, start_dt, end_dt):
        """
        Checks if [start_dt, end_dt] overlaps with any scheduled maintenance block.
        Time overlap formula: (S1 < E2) and (E1 > S2)
        """
        block = ResourceBlock.query.filter(
            ResourceBlock.resource_id == resource_id,
            ResourceBlock.start_at < end_dt,
            ResourceBlock.end_at > start_dt
        ).first()

        if block:
            return True, f"Resource is under maintenance: '{block.reason}' ({block.start_at.strftime('%d-%b %H:%M')} to {block.end_at.strftime('%d-%b %H:%M')})."
        return False, ""

    @classmethod
    def check_booking_conflict(cls, resource_id, start_dt, end_dt, exclude_booking_id=None, include_provisional=False):
        """
        Checks if [start_dt, end_dt] overlaps with any existing booking for resource_id.
        By default, checks approved bookings.
        If include_provisional is True (or setting hold_pending is true), also checks pending bookings.
        """
        query = db.session.query(BookingResource).join(BookingRequest).filter(
            BookingResource.resource_id == resource_id,
            BookingResource.start_at < end_dt,
            BookingResource.end_at > start_dt
        )

        if exclude_booking_id:
            query = query.filter(BookingResource.booking_id != exclude_booking_id)

        hold_pending = include_provisional or (SystemSetting.get_value('HOLD_PENDING_REQUESTS', 'false').lower() == 'true')
        if hold_pending:
            query = query.filter(BookingRequest.status.in_([BookingRequest.STATUS_APPROVED, BookingRequest.STATUS_PENDING]))
        else:
            query = query.filter(BookingRequest.status == BookingRequest.STATUS_APPROVED)

        conflicting_slot = query.first()
        if conflicting_slot:
            status_text = "confirmed reservation" if conflicting_slot.booking.status == BookingRequest.STATUS_APPROVED else "pending reservation"
            event_title = conflicting_slot.booking.event.title if conflicting_slot.booking.event else "Scheduled Event"
            return True, (
                f"Slot conflict: Resource already has a {status_text} for '{event_title}' "
                f"from {conflicting_slot.start_at.strftime('%d-%b %H:%M')} to {conflicting_slot.end_at.strftime('%H:%M')}."
            )

        return False, ""

    @classmethod
    def is_resource_available(cls, resource_id, start_dt, end_dt, exclude_booking_id=None):
        """
        Comprehensive resource availability validation.
        Returns (is_available, reason_str).
        """
        if end_dt <= start_dt:
            return False, "End time must be after start time."

        resource = Resource.query.get(resource_id)
        if not resource:
            return False, "Resource not found."

        if not resource.booking_allowed or resource.status != 'active':
            return False, f"Resource '{resource.name}' is currently {resource.status} and not open for booking."

        # 1. Operating hours
        is_in_hours, msg = cls.check_operating_hours(resource, start_dt, end_dt)
        if not is_in_hours:
            return False, msg

        # 2. Maintenance blocks
        has_block, msg = cls.check_maintenance_conflict(resource_id, start_dt, end_dt)
        if has_block:
            return False, msg

        # 3. Existing bookings
        has_conflict, msg = cls.check_booking_conflict(resource_id, start_dt, end_dt, exclude_booking_id=exclude_booking_id)
        if has_conflict:
            return False, msg

        return True, "Resource is available."

    @classmethod
    def get_calendar_events(cls, start_dt, end_dt, resource_id=None, category_id=None):
        """
        Retrieves all schedule intervals (Approved, Pending, Maintenance) formatted for FullCalendar.
        """
        events = []

        # 1. Approved Bookings
        booking_query = db.session.query(BookingResource).join(BookingRequest).join(Resource).filter(
            BookingResource.start_at < end_dt,
            BookingResource.end_at > start_dt,
            BookingRequest.status.in_([BookingRequest.STATUS_APPROVED, BookingRequest.STATUS_PENDING])
        )

        if resource_id:
            booking_query = booking_query.filter(BookingResource.resource_id == resource_id)
        if category_id:
            booking_query = booking_query.filter(Resource.category_id == category_id)

        for br in booking_query.all():
            is_approved = (br.booking.status == BookingRequest.STATUS_APPROVED)
            events.append({
                'id': f"booking-{br.id}",
                'title': f"{br.resource.name}: {br.booking.event.title if br.booking.event else 'Event'}",
                'start': br.start_at.isoformat(),
                'end': br.end_at.isoformat(),
                'status': br.booking.status,
                'resourceName': br.resource.name,
                'eventCategory': br.booking.event.category if br.booking.event else 'Event',
                'organiser': br.booking.requester.name if br.booking.requester else 'Unknown',
                'backgroundColor': '#ecfdf5' if is_approved else '#fffbeb',
                'textColor': '#065f46' if is_approved else '#92400e',
                'borderColor': '#10b981' if is_approved else '#f59e0b',
                'type': 'booking',
                'bookingId': br.booking_id
            })

        # 2. Maintenance Blocks
        block_query = db.session.query(ResourceBlock).join(Resource).filter(
            ResourceBlock.start_at < end_dt,
            ResourceBlock.end_at > start_dt
        )

        if resource_id:
            block_query = block_query.filter(ResourceBlock.resource_id == resource_id)
        if category_id:
            block_query = block_query.filter(Resource.category_id == category_id)

        for block in block_query.all():
            events.append({
                'id': f"block-{block.id}",
                'title': f"Maintenance: {block.resource.name} ({block.reason})",
                'start': block.start_at.isoformat(),
                'end': block.end_at.isoformat(),
                'status': 'MAINTENANCE',
                'resourceName': block.resource.name,
                'backgroundColor': '#fef2f2',
                'textColor': '#991b1b',
                'borderColor': '#ef4444',
                'type': 'maintenance'
            })

        return events
