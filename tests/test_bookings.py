import unittest
from datetime import date, time, datetime, timedelta
from app import create_app
from app.extensions import db
from app.models import User, Department, Society, ResourceCategory, Resource, Equipment, BookingRequest
from app.services.booking_service import BookingService

class BookingTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app('testing')
        self.app_context = self.app.app_context()
        self.app_context.push()
        self.client = self.app.test_client()
        db.create_all()

        dept = Department(name="Mathematics", code="MTH")
        db.session.add(dept)

        self.user = User(name="Faculty Member", email="faculty@test.du.ac.in", role="Faculty", is_active=True)
        self.user.set_password("facultypass")
        db.session.add(self.user)

        cat = ResourceCategory(name="Seminar spaces")
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

        self.lab = Resource(
            name="Lab 11",
            category_id=cat.id,
            capacity=40,
            location="IT Block",
            status="active",
            booking_allowed=True,
            approval_required=True,
            operating_hours_start="09:00",
            operating_hours_end="17:00"
        )
        db.session.add(self.lab)

        self.eq = Equipment(name="Projector", category="Projectors", total_quantity=5, is_available=True, maintenance_status="Active")
        db.session.add(self.eq)

        db.session.commit()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def test_create_multi_resource_booking(self):
        event_day = date.today() + timedelta(days=5)
        event_data = {
            'title': 'AI and Discrete Math Workshop',
            'description': 'Joint hands-on math and coding workshop.',
            'category': 'Workshop',
            'expected_attendance': 35,
            'event_date': event_day,
            'start_time': time(9, 30),
            'end_time': time(16, 30)
        }

        # Multi-resource slots: Hall for morning session (09:30 - 13:00) and Lab for afternoon (13:00 - 16:30)
        resource_slots = [
            {
                'resource_id': self.hall.id,
                'start_at': datetime.combine(event_day, time(9, 30)),
                'end_at': datetime.combine(event_day, time(13, 0))
            },
            {
                'resource_id': self.lab.id,
                'start_at': datetime.combine(event_day, time(13, 0)),
                'end_at': datetime.combine(event_day, time(16, 30))
            }
        ]

        equipment_items = [
            {
                'equipment_id': self.eq.id,
                'quantity': 2,
                'start_at': datetime.combine(event_day, time(9, 30)),
                'end_at': datetime.combine(event_day, time(16, 30))
            }
        ]

        success, booking = BookingService.create_event_booking(
            requester=self.user,
            event_data=event_data,
            resource_slots=resource_slots,
            equipment_items=equipment_items
        )

        self.assertTrue(success)
        self.assertIsNotNone(booking.id)
        self.assertEqual(booking.status, BookingRequest.STATUS_PENDING)
        self.assertEqual(len(booking.booking_resources), 2)
        self.assertEqual(len(booking.equipment_requests), 1)
        self.assertEqual(booking.equipment_requests[0].quantity, 2)

    def test_cancel_booking(self):
        event_day = date.today() + timedelta(days=4)
        event_data = {
            'title': 'Short Meeting',
            'description': 'Faculty council meeting.',
            'category': 'Meeting',
            'expected_attendance': 20,
            'event_date': event_day,
            'start_time': time(10, 0),
            'end_time': time(12, 0)
        }
        resource_slots = [{
            'resource_id': self.hall.id,
            'start_at': datetime.combine(event_day, time(10, 0)),
            'end_at': datetime.combine(event_day, time(12, 0))
        }]

        success, booking = BookingService.create_event_booking(self.user, event_data, resource_slots)
        self.assertTrue(success)

        # Cancel by requester
        cancel_success, msg = BookingService.cancel_booking(booking.id, self.user, "Speaker rescheduled")
        self.assertTrue(cancel_success)

        refreshed = BookingRequest.query.get(booking.id)
        self.assertEqual(refreshed.status, BookingRequest.STATUS_CANCELLED)
        self.assertEqual(refreshed.booking_resources[0].status, 'CANCELLED')

if __name__ == '__main__':
    unittest.main()
