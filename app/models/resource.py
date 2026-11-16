from datetime import datetime
from app.extensions import db

class ResourceCategory(db.Model):
    __tablename__ = 'resource_categories'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    description = db.Column(db.Text, nullable=True)

    resources = db.relationship('Resource', back_populates='category', lazy='dynamic')

    def __repr__(self):
        return f"<ResourceCategory {self.name}>"

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'resource_count': self.resources.count()
        }

class Resource(db.Model):
    __tablename__ = 'resources'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), unique=True, nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey('resource_categories.id'), nullable=False)
    capacity = db.Column(db.Integer, nullable=False, default=50)
    location = db.Column(db.String(150), default='College Campus')
    status = db.Column(db.String(30), default='active', nullable=False)  # active, maintenance, inactive
    booking_allowed = db.Column(db.Boolean, default=True, nullable=False)
    approval_required = db.Column(db.Boolean, default=True, nullable=False)
    operating_hours_start = db.Column(db.String(10), default='09:00', nullable=False)
    operating_hours_end = db.Column(db.String(10), default='17:00', nullable=False)
    equipment_available = db.Column(db.String(255), nullable=True)
    special_instructions = db.Column(db.Text, nullable=True)
    department_id = db.Column(db.Integer, db.ForeignKey('departments.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    category = db.relationship('ResourceCategory', back_populates='resources')
    department = db.relationship('Department', back_populates='resources')
    booking_resources = db.relationship('BookingResource', back_populates='resource', lazy='dynamic')
    maintenance_blocks = db.relationship('ResourceBlock', back_populates='resource', lazy='dynamic', cascade='all, delete-orphan')

    __table_args__ = (
        db.CheckConstraint('capacity > 0', name='check_resource_positive_capacity'),
    )

    def is_available_for_booking(self):
        return self.status == 'active' and self.booking_allowed

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'category': self.category.name if self.category else None,
            'category_id': self.category_id,
            'capacity': self.capacity,
            'location': self.location,
            'status': self.status,
            'booking_allowed': self.booking_allowed,
            'approval_required': self.approval_required,
            'operating_hours': f"{self.operating_hours_start} - {self.operating_hours_end}",
            'operating_hours_start': self.operating_hours_start,
            'operating_hours_end': self.operating_hours_end,
            'equipment_available': self.equipment_available,
            'special_instructions': self.special_instructions,
            'department': self.department.name if self.department else None
        }

    def __repr__(self):
        return f"<Resource {self.name} ({self.category.name if self.category else 'No Category'})>"

class ResourceBlock(db.Model):
    __tablename__ = 'resource_blocks'

    id = db.Column(db.Integer, primary_key=True)
    resource_id = db.Column(db.Integer, db.ForeignKey('resources.id', ondelete='CASCADE'), nullable=False)
    start_at = db.Column(db.DateTime, nullable=False, index=True)
    end_at = db.Column(db.DateTime, nullable=False, index=True)
    reason = db.Column(db.String(255), nullable=False)
    created_by_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    resource = db.relationship('Resource', back_populates='maintenance_blocks')
    created_by = db.relationship('User')

    __table_args__ = (
        db.CheckConstraint('end_at > start_at', name='check_block_end_after_start'),
    )

    def to_dict(self):
        return {
            'id': self.id,
            'resource_id': self.resource_id,
            'resource_name': self.resource.name if self.resource else None,
            'start_at': self.start_at.isoformat(),
            'end_at': self.end_at.isoformat(),
            'reason': self.reason,
            'created_by': self.created_by.name if self.created_by else 'Admin'
        }

    def __repr__(self):
        return f"<ResourceBlock Resource={self.resource_id} [{self.start_at} - {self.end_at}]>"
