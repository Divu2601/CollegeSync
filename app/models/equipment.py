from datetime import datetime
from app.extensions import db

class Equipment(db.Model):
    __tablename__ = 'equipments'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    category = db.Column(db.String(50), nullable=False)  # Projector, Audio/Speaker, Laptop, Furniture, etc.
    total_quantity = db.Column(db.Integer, nullable=False, default=1)
    condition = db.Column(db.String(50), default='Good', nullable=False)  # Excellent, Good, Fair, Maintenance
    storage_location = db.Column(db.String(100), default='AV Room / Store')
    maintenance_status = db.Column(db.String(50), default='Active', nullable=False)  # Active, Under Maintenance, Retired
    is_available = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    equipment_requests = db.relationship('EquipmentRequest', back_populates='equipment', lazy='dynamic')

    __table_args__ = (
        db.CheckConstraint('total_quantity >= 0', name='check_equipment_positive_total'),
    )

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'category': self.category,
            'total_quantity': self.total_quantity,
            'condition': self.condition,
            'storage_location': self.storage_location,
            'maintenance_status': self.maintenance_status,
            'is_available': self.is_available
        }

    def __repr__(self):
        return f"<Equipment {self.name} (Total: {self.total_quantity})>"

class EquipmentRequest(db.Model):
    __tablename__ = 'equipment_requests'

    id = db.Column(db.Integer, primary_key=True)
    booking_id = db.Column(db.Integer, db.ForeignKey('booking_requests.id', ondelete='CASCADE'), nullable=False)
    equipment_id = db.Column(db.Integer, db.ForeignKey('equipments.id'), nullable=False)
    quantity = db.Column(db.Integer, nullable=False, default=1)
    start_at = db.Column(db.DateTime, nullable=False, index=True)
    end_at = db.Column(db.DateTime, nullable=False, index=True)

    # Relationships
    booking = db.relationship('BookingRequest', back_populates='equipment_requests')
    equipment = db.relationship('Equipment', back_populates='equipment_requests')

    __table_args__ = (
        db.CheckConstraint('quantity > 0', name='check_equipment_request_positive_quantity'),
        db.CheckConstraint('end_at > start_at', name='check_equipment_req_end_after_start'),
    )

    def to_dict(self):
        return {
            'id': self.id,
            'booking_id': self.booking_id,
            'equipment_id': self.equipment_id,
            'equipment_name': self.equipment.name if self.equipment else None,
            'quantity': self.quantity,
            'start_at': self.start_at.isoformat(),
            'end_at': self.end_at.isoformat()
        }

    def __repr__(self):
        return f"<EquipmentRequest Booking={self.booking_id} Eq={self.equipment_id} Qty={self.quantity}>"
