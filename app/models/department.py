from datetime import datetime
from app.extensions import db

class Department(db.Model):
    __tablename__ = 'departments'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    code = db.Column(db.String(20), unique=True, nullable=True)
    description = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    users = db.relationship('User', back_populates='department', lazy='dynamic')
    events = db.relationship('Event', back_populates='department', lazy='dynamic')
    resources = db.relationship('Resource', back_populates='department', lazy='dynamic')

    def __repr__(self):
        return f"<Department {self.name}>"

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'code': self.code,
            'description': self.description
        }
