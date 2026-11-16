from datetime import datetime
from app.extensions import db
from app.models.notification import Notification
from app.models.user import User

class NotificationService:
    @classmethod
    def create_notification(cls, user_id, title, message, link=None):
        """Creates an in-app notification for a given user."""
        notification = Notification(
            user_id=user_id,
            title=title,
            message=message,
            link=link
        )
        db.session.add(notification)
        return notification

    @classmethod
    def notify_admins(cls, title, message, link=None):
        """Dispatches an in-app notification to all active Administrators."""
        admins = User.query.filter_by(role='Administrator', is_active=True).all()
        created = []
        for admin in admins:
            created.append(cls.create_notification(admin.id, title, message, link))
        return created

    @classmethod
    def notify_requester(cls, booking, action, remarks=None):
        """Notifies the requester of status transitions."""
        event_title = booking.event.title if booking.event else f"Booking #{booking.id}"
        link = f"/bookings/{booking.id}"

        if action == 'APPROVED':
            title = f"Booking Approved: {event_title}"
            msg = f"Your booking request for '{event_title}' has been approved by the administration."
            if remarks:
                msg += f" Remarks: {remarks}"
        elif action == 'REJECTED':
            title = f"Booking Rejected: {event_title}"
            msg = f"Your booking request for '{event_title}' was declined."
            if remarks:
                msg += f" Reason: {remarks}"
        elif action == 'CANCELLED':
            title = f"Booking Cancelled: {event_title}"
            msg = f"The booking for '{event_title}' has been cancelled."
            if remarks:
                msg += f" Reason: {remarks}"
        else:
            title = f"Booking Update: {event_title}"
            msg = f"Your booking status has changed to {action}."

        return cls.create_notification(booking.requester_id, title, msg, link)

    @classmethod
    def get_unread_count(cls, user_id):
        return Notification.query.filter_by(user_id=user_id, is_read=False).count()

    @classmethod
    def mark_all_as_read(cls, user_id):
        Notification.query.filter_by(user_id=user_id, is_read=False).update({'is_read': True})
        db.session.commit()
