from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin
from app.extensions import db, login_manager

class User(UserMixin, db.Model):
    __tablename__ = 'users'

    ROLES = [
        'Administrator',
        'Faculty',
        'Staff',
        'Student',
        'Society Coordinator',
        'Department Coordinator'
    ]

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(50), nullable=False, default='Student')
    department_id = db.Column(db.Integer, db.ForeignKey('departments.id'), nullable=True)
    phone = db.Column(db.String(20), nullable=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    department = db.relationship('Department', back_populates='users')
    society_memberships = db.relationship('SocietyMembership', back_populates='user', cascade='all, delete-orphan')
    events = db.relationship('Event', back_populates='organiser', lazy='dynamic')
    booking_requests = db.relationship('BookingRequest', back_populates='requester', lazy='dynamic')
    notifications = db.relationship('Notification', back_populates='user', lazy='dynamic', cascade='all, delete-orphan')

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def is_admin(self):
        return self.role == 'Administrator'

    def is_coordinator(self):
        return self.role in ('Society Coordinator', 'Department Coordinator', 'Administrator')

    def can_request(self):
        return self.is_active

    def can_approve(self):
        return self.is_admin()

    def get_societies(self):
        return [m.society for m in self.society_memberships]

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'email': self.email,
            'role': self.role,
            'department': self.department.name if self.department else None,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

    def __repr__(self):
        return f"<User {self.name} ({self.role})>"

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))
