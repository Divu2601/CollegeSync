import unittest
from datetime import date, time, datetime, timedelta
from app import create_app
from app.extensions import db
from app.models import User, ResourceCategory, Resource, ResourceBlock, BookingRequest
from app.services.booking_service import BookingService
from app.services.approval_service import ApprovalService
from app.services.availability_service import AvailabilityService

class ConflictDetectionTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app('testing')
        self.app_context = self.app.app_context()
        self.app_context.push()
        self.client = self.app.test_client()
        db.create_all()

        self.admin = User(name="Admin", email="admin@test.du.ac.in", role="Administrator")
        self.admin.set_password("pass")
        db.session.add(self.admin)

        self.user1 = User(name="User 1", email="u1@test.du.ac.in", role="Faculty")
        self.user1.set_password("pass")
        db.session.add(self.user1)

        self.user2 = User(name="User 2", email="u2@test.du.ac.in", role="Student")
        self.user2.set_password("pass")
        db.session.add(self.user2)

        cat = ResourceCategory(name="Seminar Hall")
        db.session.add(cat)
        db.session.flush()

        self.hall = Resource(
            name="Old Seminar Hall",
            category_id=cat.id,
            capacity=100,
            location="Ground Floor",
            status="active",
            booking_allowed=True,
            approval_required=True,
            operating_hours_start="09:00",
            operating_hours_end="17:00"
        )
        db.session.add(self.hall)
        db.session.commit()

        self.target_date = date.today() + timedelta(days=7)

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def test_adjacent_time_slots_allowed(self):
        """
        Bookings ending and starting at the exact same time (e.g. 10:00 - 12:00 and 12:00 - 14:00)
        do NOT conflict and must be allowed.
        """
        # Event 1: 10:00 - 12:00
        slot1_start = datetime.combine(self.target_date, time(10, 0))
        slot1_end = datetime.combine(self.target_date, time(12, 0))

        success1, b1 = BookingService.create_event_booking(
            self.user1,
            {'title': 'Event 1', 'description': 'Morning', 'category': 'Academic', 'expected_attendance': 40,
             'event_date': self.target_date, 'start_time': time(10, 0), 'end_time': time(12, 0)},
            [{'resource_id': self.hall.id, 'start_at': slot1_start, 'end_at': slot1_end}]
        )
        self.assertTrue(success1)
        # Approve Event 1
        app_res1, _ = ApprovalService.approve_booking(b1.id, self.admin)
        self.assertTrue(app_res1)

        # Event 2: Adjacent slot 12:00 - 14:00
        slot2_start = datetime.combine(self.target_date, time(12, 0))
        slot2_end = datetime.combine(self.target_date, time(14, 0))

        success2, b2 = BookingService.create_event_booking(
            self.user2,
            {'title': 'Event 2', 'description': 'Afternoon', 'category': 'Seminar', 'expected_attendance': 40,
             'event_date': self.target_date, 'start_time': time(12, 0), 'end_time': time(14, 0)},
            [{'resource_id': self.hall.id, 'start_at': slot2_start, 'end_at': slot2_end}]
        )
        self.assertTrue(success2, "Adjacent booking starting at 12:00 should be allowed when prior ends at 12:00")

    def test_overlapping_slot_with_approved_booking_rejected(self):
        """
        If an approved booking exists from 10:00 to 12:00,
        a request for 11:00 to 13:00 must be detected as a conflict!
        (S1 < E2) and (E1 > S2): (10 < 13) and (12 > 11) is True -> Conflict!
        """
        # Approved booking 10:00 - 12:00
        s1 = datetime.combine(self.target_date, time(10, 0))
        e1 = datetime.combine(self.target_date, time(12, 0))
        _, b1 = BookingService.create_event_booking(
            self.user1,
            {'title': 'Coding Competition', 'description': 'Morning', 'category': 'Technical', 'expected_attendance': 50,
             'event_date': self.target_date, 'start_time': time(10, 0), 'end_time': time(12, 0)},
            [{'resource_id': self.hall.id, 'start_at': s1, 'end_at': e1}]
        )
        ApprovalService.approve_booking(b1.id, self.admin)

        # Attempt to book 11:00 - 13:00 (Overlapping!)
        s2 = datetime.combine(self.target_date, time(11, 0))
        e2 = datetime.combine(self.target_date, time(13, 0))
        success, res = BookingService.create_event_booking(
            self.user2,
            {'title': 'Seminar Clash', 'description': 'Overlap', 'category': 'Seminar', 'expected_attendance': 30,
             'event_date': self.target_date, 'start_time': time(11, 0), 'end_time': time(13, 0)},
            [{'resource_id': self.hall.id, 'start_at': s2, 'end_at': e2}]
        )
        self.assertFalse(success)
        self.assertIn("Slot conflict", res)

    def test_booking_during_maintenance_blocked(self):
        """
        Bookings overlapping with a scheduled ResourceBlock maintenance window must be rejected.
        """
        m_start = datetime.combine(self.target_date, time(14, 0))
        m_end = datetime.combine(self.target_date, time(17, 0))
        block = ResourceBlock(
            resource_id=self.hall.id,
            start_at=m_start,
            end_at=m_end,
            reason="Audio/Video Equipment Repair",
            created_by_id=self.admin.id
        )
        db.session.add(block)
        db.session.commit()

        # Attempt to book during maintenance (15:00 - 16:30)
        req_start = datetime.combine(self.target_date, time(15, 0))
        req_end = datetime.combine(self.target_date, time(16, 30))
        success, res = BookingService.create_event_booking(
            self.user1,
            {'title': 'Guest Lecture', 'description': 'Lecture', 'category': 'Academic', 'expected_attendance': 40,
             'event_date': self.target_date, 'start_time': time(15, 0), 'end_time': time(16, 30)},
            [{'resource_id': self.hall.id, 'start_at': req_start, 'end_at': req_end}]
        )
        self.assertFalse(success)
        self.assertIn("under maintenance", res)

    def test_outside_operating_hours_blocked(self):
        """
        Hall operating hours are 09:00 - 17:00.
        A booking starting at 08:00 or ending at 18:00 must be rejected.
        """
        early_start = datetime.combine(self.target_date, time(8, 0))
        early_end = datetime.combine(self.target_date, time(10, 0))
        success, res = BookingService.create_event_booking(
            self.user1,
            {'title': 'Early Event', 'description': 'Early', 'category': 'Other', 'expected_attendance': 20,
             'event_date': self.target_date, 'start_time': time(8, 0), 'end_time': time(10, 0)},
            [{'resource_id': self.hall.id, 'start_at': early_start, 'end_at': early_end}]
        )
        self.assertFalse(success)
        self.assertIn("outside operating hours", res)

if __name__ == '__main__':
    unittest.main()
