from datetime import datetime
from app.extensions import db
from app.models.equipment import Equipment, EquipmentRequest
from app.models.booking import BookingRequest

class EquipmentService:
    @classmethod
    def get_max_concurrent_usage(cls, equipment_id, start_dt, end_dt, exclude_booking_id=None):
        """
        Calculates the maximum concurrent units allocated to APPROVED bookings
        at any instant during the interval [start_dt, end_dt].
        Uses a sweep-line algorithm over time transition points.
        """
        query = db.session.query(EquipmentRequest).join(BookingRequest).filter(
            EquipmentRequest.equipment_id == equipment_id,
            EquipmentRequest.start_at < end_dt,
            EquipmentRequest.end_at > start_dt,
            BookingRequest.status == BookingRequest.STATUS_APPROVED
        )

        if exclude_booking_id:
            query = query.filter(EquipmentRequest.booking_id != exclude_booking_id)

        overlapping_requests = query.all()
        if not overlapping_requests:
            return 0

        # Timeline sweep
        points = []
        for req in overlapping_requests:
            # Clamp points to the query window [start_dt, end_dt]
            p_start = max(req.start_at, start_dt)
            p_end = min(req.end_at, end_dt)
            # Tuple: (timestamp, change_in_quantity, priority)
            # When timestamps match, end (-qty) comes before start (+qty) so contiguous slots don't double count
            points.append((p_start, req.quantity, 1))
            points.append((p_end, -req.quantity, -1))

        # Sort: first by timestamp, then by priority (-1 ends before +1 starts)
        points.sort(key=lambda x: (x[0], x[2]))

        current_usage = 0
        peak_usage = 0
        for pt_time, delta_qty, _ in points:
            current_usage += delta_qty
            if current_usage > peak_usage:
                peak_usage = current_usage

        return peak_usage

    @classmethod
    def get_available_quantity(cls, equipment_id, start_dt, end_dt, exclude_booking_id=None):
        """
        Returns the number of unallocated units available throughout [start_dt, end_dt].
        """
        equipment = Equipment.query.get(equipment_id)
        if not equipment or not equipment.is_available or equipment.maintenance_status != 'Active':
            return 0

        peak_allocated = cls.get_max_concurrent_usage(equipment_id, start_dt, end_dt, exclude_booking_id)
        available = max(0, equipment.total_quantity - peak_allocated)
        return available

    @classmethod
    def check_equipment_availability(cls, equipment_id, requested_qty, start_dt, end_dt, exclude_booking_id=None):
        """
        Validates if requested_qty can be fulfilled.
        Returns (is_available, remaining_available, error_message).
        """
        if requested_qty <= 0:
            return False, 0, "Requested quantity must be at least 1."

        equipment = Equipment.query.get(equipment_id)
        if not equipment:
            return False, 0, "Equipment not found."

        if not equipment.is_available or equipment.maintenance_status != 'Active':
            return False, 0, f"Equipment '{equipment.name}' is currently {equipment.maintenance_status} and unavailable for booking."

        if requested_qty > equipment.total_quantity:
            return False, 0, f"Requested quantity ({requested_qty}) exceeds college total stock ({equipment.total_quantity}) for {equipment.name}."

        available_qty = cls.get_available_quantity(equipment_id, start_dt, end_dt, exclude_booking_id)
        if requested_qty > available_qty:
            return False, available_qty, (
                f"Insufficient stock for '{equipment.name}'. Requested: {requested_qty}, "
                f"Available in requested slot: {available_qty} (Total: {equipment.total_quantity})."
            )

        return True, available_qty, ""
