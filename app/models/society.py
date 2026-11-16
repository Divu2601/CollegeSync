from datetime import datetime
from app.extensions import db

class Society(db.Model):
    __tablename__ = 'societies'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    category = db.Column(db.String(50), nullable=False, default='Cultural')  # Cultural, Technical, Academic, Sports, Social
    description = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    memberships = db.relationship('SocietyMembership', back_populates='society', cascade='all, delete-orphan')
    events = db.relationship('Event', back_populates='society', lazy='dynamic')

    def __repr__(self):
        return f"<Society {self.name}>"

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'category': self.category,
            'description': self.description
        }

class SocietyMembership(db.Model):
    __tablename__ = 'society_memberships'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    society_id = db.Column(db.Integer, db.ForeignKey('societies.id', ondelete='CASCADE'), nullable=False)
    membership_role = db.Column(db.String(50), default='Member')  # President, Secretary, Coordinator, Member
    joined_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User', back_populates='society_memberships')
    society = db.relationship('Society', back_populates='memberships')

    __table_args__ = (
        db.UniqueConstraint('user_id', 'society_id', name='uq_user_society'),
    )

    def __repr__(self):
        return f"<Membership User={self.user_id} Society={self.society_id} Role={self.membership_role}>"
