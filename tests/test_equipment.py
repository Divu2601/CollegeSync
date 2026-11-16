import unittest
from datetime import date, time, datetime, timedelta
from app import create_app
from app.extensions import db
from app.models import User, ResourceCategory, Resource, Equipment, EquipmentRequest, BookingRequest
from app.services.booking_service import BookingService
from app.services.approval_service import ApprovalService
from app.services.equipment_service import EquipmentService

class EquipmentAllocationTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app('testing')
        self.app_context = self.app.app_context()
        self.app_context.push()
        self.client = self.app.test_client()
        db.create_all()

        self.admin = User(name="Admin", email="admin@test.du.ac.in", role="Administrator")
        self.admin.set_password("pass")
        db.session.add(self.admin)

        self.user = User(name="Faculty", email="faculty@test.du.ac.in", role="Faculty")
        self.user.set_password("pass")
        db.session.add(self.user)

        cat = ResourceCategory(name="Seminar")
        db.session.add(cat)
        db.session.flush()

        self.hall = Resource(
            name="Seminar Hall A",
            category_id=cat.id,
            capacity=100,
            location="Campus",
            status="active",
            booking_allowed=True,
            approval_required=True,
            operating_hours_start="09:00",
            operating_hours_end="17:00"
        )
        db.session.add(self.hall)

        # 5 Projectors in stock
        self.projector = Equipment(
            name="Projector",
            category="Projectors",
            total_quantity=5,
            condition="Excellent",
            storage_location="AV Room",
            maintenance_status="Active",
            is_available=True
        )
        db.session.add(self.projector)
        db.session.commit()

        self.event_date = date.today() + timedelta(days=8)

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def test_equipment_concurrency_allocation(self):
        """
        Tests dynamic concurrency:
        Total stock = 5 projectors.
        Booking 1 reserves 3 projectors from 10:00 to 14:00 (Approved).
        Booking 2 requests 3 projectors from 11:00 to 13:00 -> Exceeds remaining (2) -> Rejected.
        Booking 3 requests 2 projectors from 11:00 to 13:00 -> Fits exactly (3+2=5) -> Allowed.
        Booking 4 requests 3 projectors from 14:00 to 16:00 -> Contiguous non-overlapping -> Allowed.
        """
        # Booking 1: 3 projectors, 10:00 - 14:00
        s1 = datetime.combine(self.event_date, time(10, 0))
        e1 = datetime.combine(self.event_date, time(14, 0))
        ok1, b1 = BookingService.create_event_booking(
            self.user,
            {'title': 'Workshop 1', 'description': 'desc', 'category': 'Workshop', 'expected_attendance': 40,
             'event_date': self.event_date, 'start_time': time(10, 0), 'end_time': time(14, 0)},
            [{'resource_id': self.hall.id, 'start_at': s1, 'end_at': e1}],
            [{'equipment_id': self.projector.id, 'quantity': 3, 'start_at': s1, 'end_at': e1}]
        )
        self.assertTrue(ok1)
        ApprovalService.approve_booking(b1.id, self.admin)

        # Room 2 for concurrent events
        self.room2 = Resource(name="Room 2", category_id=self.hall.category_id, capacity=50, status="active",
                              booking_allowed=True, approval_required=True, operating_hours_start="09:00", operating_hours_end="17:00")
        db.session.add(self.room2)
        db.session.commit()

        # Check remaining quantity during 11:00 - 13:00
        s2 = datetime.combine(self.event_date, time(11, 0))
        e2 = datetime.combine(self.event_date, time(13, 0))
        avail_qty = EquipmentService.get_available_quantity(self.projector.id, s2, e2)
        self.assertEqual(avail_qty, 2, "Out of 5, 3 are reserved, so exactly 2 should be available")

        # Booking 2: requesting 3 projectors during 11:00 - 13:00 -> Insufficient!
        ok2, err2 = BookingService.create_event_booking(
            self.user,
            {'title': 'Workshop 2', 'description': 'desc', 'category': 'Workshop', 'expected_attendance': 30,
             'event_date': self.event_date, 'start_time': time(11, 0), 'end_time': time(13, 0)},
            [{'resource_id': self.room2.id, 'start_at': s2, 'end_at': e2}],
            [{'equipment_id': self.projector.id, 'quantity': 3, 'start_at': s2, 'end_at': e2}]
        )
        self.assertFalse(ok2)
        self.assertIn("Insufficient stock", err2)

        # Booking 3: requesting 2 projectors during 11:00 - 13:00 -> Fits!
        ok3, b3 = BookingService.create_event_booking(
            self.user,
            {'title': 'Workshop 3', 'description': 'desc', 'category': 'Workshop', 'expected_attendance': 30,
             'event_date': self.event_date, 'start_time': time(11, 0), 'end_time': time(13, 0)},
            [{'resource_id': self.room2.id, 'start_at': s2, 'end_at': e2}],
            [{'equipment_id': self.projector.id, 'quantity': 2, 'start_at': s2, 'end_at': e2}]
        )
        self.assertTrue(ok3, "2 units should be accepted since remaining capacity is 2")

        # Booking 4: requesting 3 projectors from 14:00 to 16:00 (contiguous after Booking 1 ends at 14:00)
        s4 = datetime.combine(self.event_date, time(14, 0))
        e4 = datetime.combine(self.event_date, time(16, 0))
        ok4, b4 = BookingService.create_event_booking(
            self.user,
            {'title': 'Workshop 4', 'description': 'desc', 'category': 'Workshop', 'expected_attendance': 30,
             'event_date': self.event_date, 'start_time': time(14, 0), 'end_time': time(16, 0)},
            [{'resource_id': self.hall.id, 'start_at': s4, 'end_at': e4}],
            [{'equipment_id': self.projector.id, 'quantity': 3, 'start_at': s4, 'end_at': e4}]
        )
        self.assertTrue(ok4, "Equipment should be available immediately after prior booking finishes at 14:00")

if __name__ == '__main__':
    unittest.main()
