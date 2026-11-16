from datetime import datetime
from app.extensions import db

class Event(db.Model):
    __tablename__ = 'events'

    CATEGORIES = [
        'Academic',
        'Technical',
        'Cultural',
        'Sports',
        'Workshop',
        'Seminar',
        'Competition',
        'Meeting',
        'Other'
    ]

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(150), nullable=False)
    description = db.Column(db.Text, nullable=False)
    category = db.Column(db.String(50), nullable=False, default='Academic')
    organiser_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    department_id = db.Column(db.Integer, db.ForeignKey('departments.id'), nullable=True)
    society_id = db.Column(db.Integer, db.ForeignKey('societies.id'), nullable=True)
    expected_attendance = db.Column(db.Integer, nullable=False, default=50)
    event_date = db.Column(db.Date, nullable=False)
    start_time = db.Column(db.Time, nullable=False)
    end_time = db.Column(db.Time, nullable=False)
    requirements = db.Column(db.Text, nullable=True)
    supporting_document = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    organiser = db.relationship('User', back_populates='events')
    department = db.relationship('Department', back_populates='events')
    society = db.relationship('Society', back_populates='events')
    booking_requests = db.relationship('BookingRequest', back_populates='event', cascade='all, delete-orphan')

    __table_args__ = (
        db.CheckConstraint('expected_attendance > 0', name='check_event_positive_attendance'),
    )

    def to_dict(self):
        return {
            'id': self.id,
            'title': self.title,
            'description': self.description,
            'category': self.category,
            'organiser': self.organiser.name if self.organiser else None,
            'organiser_id': self.organiser_id,
            'department': self.department.name if self.department else None,
            'society': self.society.name if self.society else None,
            'expected_attendance': self.expected_attendance,
            'event_date': self.event_date.isoformat() if self.event_date else None,
            'start_time': self.start_time.strftime('%H:%M') if self.start_time else None,
            'end_time': self.end_time.strftime('%H:%M') if self.end_time else None,
            'requirements': self.requirements,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

    def __repr__(self):
        return f"<Event {self.title} ({self.category})>"
