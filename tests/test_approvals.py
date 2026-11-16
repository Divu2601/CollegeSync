import unittest
from datetime import date, time, datetime, timedelta
from app import create_app
from app.extensions import db
from app.models import User, ResourceCategory, Resource, BookingRequest, ApprovalHistory
from app.services.booking_service import BookingService
from app.services.approval_service import ApprovalService

class ApprovalConcurrencyTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app('testing')
        self.app_context = self.app.app_context()
        self.app_context.push()
        self.client = self.app.test_client()
        db.create_all()

        self.admin1 = User(name="Admin 1", email="admin1@test.du.ac.in", role="Administrator")
        self.admin1.set_password("pass")
        db.session.add(self.admin1)

        self.admin2 = User(name="Admin 2", email="admin2@test.du.ac.in", role="Administrator")
        self.admin2.set_password("pass")
        db.session.add(self.admin2)

        self.userA = User(name="Student A", email="studentA@test.du.ac.in", role="Student")
        self.userA.set_password("pass")
        db.session.add(self.userA)

        self.userB = User(name="Student B", email="studentB@test.du.ac.in", role="Student")
        self.userB.set_password("pass")
        db.session.add(self.userB)

        cat = ResourceCategory(name="Seminar Space")
        db.session.add(cat)
        db.session.flush()

        self.hall = Resource(
            name="New Seminar Hall",
            category_id=cat.id,
            capacity=150,
            location="Campus",
            status="active",
            booking_allowed=True,
            approval_required=True,
            operating_hours_start="09:00",
            operating_hours_end="17:00"
        )
        db.session.add(self.hall)
        db.session.commit()

        self.event_date = date.today() + timedelta(days=6)

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def test_concurrent_approval_race_condition(self):
        """
        Critical Test:
        Two pending requests exist for the same hall at overlapping times.
        When two administrators attempt to approve their requests,
        EXACTLY ONE must succeed and the second must be BLOCKED!
        """
        # User A submits request for 10:00 - 14:00
        start_A = datetime.combine(self.event_date, time(10, 0))
        end_A = datetime.combine(self.event_date, time(14, 0))
        ok_A, booking_A = BookingService.create_event_booking(
            self.userA,
            {'title': 'Hackathon Prelims', 'description': 'Coding', 'category': 'Technical', 'expected_attendance': 60,
             'event_date': self.event_date, 'start_time': time(10, 0), 'end_time': time(14, 0)},
            [{'resource_id': self.hall.id, 'start_at': start_A, 'end_at': end_A}]
        )
        self.assertTrue(ok_A)
        self.assertEqual(booking_A.status, BookingRequest.STATUS_PENDING)

        # User B submits overlapping request for 12:00 - 16:00
        start_B = datetime.combine(self.event_date, time(12, 0))
        end_B = datetime.combine(self.event_date, time(16, 0))
        ok_B, booking_B = BookingService.create_event_booking(
            self.userB,
            {'title': 'Drama Rehearsal', 'description': 'Acting', 'category': 'Cultural', 'expected_attendance': 40,
             'event_date': self.event_date, 'start_time': time(12, 0), 'end_time': time(16, 0)},
            [{'resource_id': self.hall.id, 'start_at': start_B, 'end_at': end_B}]
        )
        self.assertTrue(ok_B)
        self.assertEqual(booking_B.status, BookingRequest.STATUS_PENDING)

        # Admin 1 approves Booking A
        approved_A, msg_A = ApprovalService.approve_booking(booking_A.id, self.admin1, "Approved Hackathon")
        self.assertTrue(approved_A, f"Approval of A should succeed: {msg_A}")
        self.assertEqual(BookingRequest.query.get(booking_A.id).status, BookingRequest.STATUS_APPROVED)

        # Admin 2 now attempts to approve Booking B (overlaps with A)
        approved_B, msg_B = ApprovalService.approve_booking(booking_B.id, self.admin2, "Approved Drama")
        self.assertFalse(approved_B, "Approval of B MUST be blocked because A is already approved!")
        self.assertIn("conflict", msg_B.lower())

        # Booking B remains in PENDING state (or ready to be rejected with remarks)
        self.assertEqual(BookingRequest.query.get(booking_B.id).status, BookingRequest.STATUS_PENDING)

    def test_rejection_with_reason_and_audit(self):
        start_dt = datetime.combine(self.event_date, time(10, 0))
        end_dt = datetime.combine(self.event_date, time(12, 0))
        ok, booking = BookingService.create_event_booking(
            self.userA,
            {'title': 'Debate', 'description': 'Debating', 'category': 'Academic', 'expected_attendance': 25,
             'event_date': self.event_date, 'start_time': time(10, 0), 'end_time': time(12, 0)},
            [{'resource_id': self.hall.id, 'start_at': start_dt, 'end_at': end_dt}]
        )
        self.assertTrue(ok)

        # Admin rejects with reason
        rejected, msg = ApprovalService.reject_booking(booking.id, self.admin1, "Internal administrative meeting priority")
        self.assertTrue(rejected)

        refreshed = BookingRequest.query.get(booking.id)
        self.assertEqual(refreshed.status, BookingRequest.STATUS_REJECTED)
        self.assertEqual(refreshed.rejection_reason, "Internal administrative meeting priority")
        self.assertEqual(len(refreshed.approval_history), 1)
        self.assertEqual(refreshed.approval_history[0].action, "REJECTED")

if __name__ == '__main__':
    unittest.main()
