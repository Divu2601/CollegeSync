from datetime import datetime
from app.extensions import db

class BookingRequest(db.Model):
    __tablename__ = 'booking_requests'

    STATUS_PENDING = 'PENDING'
    STATUS_APPROVED = 'APPROVED'
    STATUS_REJECTED = 'REJECTED'
    STATUS_CANCELLED = 'CANCELLED'
    STATUS_COMPLETED = 'COMPLETED'

    STATUSES = [
        STATUS_PENDING,
        STATUS_APPROVED,
        STATUS_REJECTED,
        STATUS_CANCELLED,
        STATUS_COMPLETED
    ]

    id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(db.Integer, db.ForeignKey('events.id', ondelete='CASCADE'), nullable=False)
    requester_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    status = db.Column(db.String(30), default=STATUS_PENDING, nullable=False, index=True)
    submitted_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    admin_notes = db.Column(db.Text, nullable=True)
    rejection_reason = db.Column(db.Text, nullable=True)
    cancellation_reason = db.Column(db.Text, nullable=True)

    # Relationships
    event = db.relationship('Event', back_populates='booking_requests')
    requester = db.relationship('User', back_populates='booking_requests')
    booking_resources = db.relationship('BookingResource', back_populates='booking', cascade='all, delete-orphan')
    equipment_requests = db.relationship('EquipmentRequest', back_populates='booking', cascade='all, delete-orphan')
    approval_history = db.relationship('ApprovalHistory', back_populates='booking', cascade='all, delete-orphan', order_by='ApprovalHistory.timestamp.desc()')

    def is_pending(self):
        return self.status == self.STATUS_PENDING

    def is_approved(self):
        return self.status == self.STATUS_APPROVED

    def is_cancellable(self):
        return self.status in (self.STATUS_PENDING, self.STATUS_APPROVED)

    def to_dict(self):
        return {
            'id': self.id,
            'event_id': self.event_id,
            'event_title': self.event.title if self.event else None,
            'requester': self.requester.name if self.requester else None,
            'requester_id': self.requester_id,
            'status': self.status,
            'submitted_at': self.submitted_at.isoformat() if self.submitted_at else None,
            'resources': [br.to_dict() for br in self.booking_resources],
            'equipment': [er.to_dict() for er in self.equipment_requests],
            'rejection_reason': self.rejection_reason,
            'cancellation_reason': self.cancellation_reason
        }

    def __repr__(self):
        return f"<BookingRequest {self.id} [{self.status}] Event={self.event_id}>"

class BookingResource(db.Model):
    __tablename__ = 'booking_resources'

    id = db.Column(db.Integer, primary_key=True)
    booking_id = db.Column(db.Integer, db.ForeignKey('booking_requests.id', ondelete='CASCADE'), nullable=False)
    resource_id = db.Column(db.Integer, db.ForeignKey('resources.id'), nullable=False)
    start_at = db.Column(db.DateTime, nullable=False, index=True)
    end_at = db.Column(db.DateTime, nullable=False, index=True)
    status = db.Column(db.String(30), default='PENDING', nullable=False)  # PENDING, APPROVED, CANCELLED

    booking = db.relationship('BookingRequest', back_populates='booking_resources')
    resource = db.relationship('Resource', back_populates='booking_resources')

    __table_args__ = (
        db.CheckConstraint('end_at > start_at', name='check_resource_booking_end_after_start'),
    )

    def to_dict(self):
        return {
            'id': self.id,
            'booking_id': self.booking_id,
            'resource_id': self.resource_id,
            'resource_name': self.resource.name if self.resource else None,
            'resource_category': self.resource.category.name if self.resource and self.resource.category else None,
            'start_at': self.start_at.isoformat(),
            'end_at': self.end_at.isoformat(),
            'status': self.status
        }

    def __repr__(self):
        return f"<BookingResource Booking={self.booking_id} Res={self.resource_id} [{self.start_at} - {self.end_at}]>"

class ApprovalHistory(db.Model):
    __tablename__ = 'approval_histories'

    id = db.Column(db.Integer, primary_key=True)
    booking_id = db.Column(db.Integer, db.ForeignKey('booking_requests.id', ondelete='CASCADE'), nullable=False)
    admin_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    action = db.Column(db.String(30), nullable=False)  # APPROVED, REJECTED, CANCELLED
    remarks = db.Column(db.Text, nullable=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    booking = db.relationship('BookingRequest', back_populates='approval_history')
    admin = db.relationship('User')

    def to_dict(self):
        return {
            'id': self.id,
            'booking_id': self.booking_id,
            'admin': self.admin.name if self.admin else 'System Admin',
            'action': self.action,
            'remarks': self.remarks,
            'timestamp': self.timestamp.isoformat()
        }

    def __repr__(self):
        return f"<ApprovalHistory Booking={self.booking_id} Action={self.action} by User={self.admin_id}>"

class SystemSetting(db.Model):
    __tablename__ = 'system_settings'

    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(80), unique=True, nullable=False)
    value = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=True)

    @classmethod
    def get_value(cls, key, default=None):
        setting = cls.query.filter_by(key=key).first()
        return setting.value if setting else default

    @classmethod
    def set_value(cls, key, value, description=None):
        setting = cls.query.filter_by(key=key).first()
        if not setting:
            setting = cls(key=key, value=str(value), description=description)
            db.session.add(setting)
        else:
            setting.value = str(value)
            if description:
                setting.description = description
        db.session.commit()
        return setting

    def __repr__(self):
        return f"<SystemSetting {self.key}={self.value}>"
