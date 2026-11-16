from flask import Blueprint, render_template, redirect, url_for, flash
from flask_login import login_required, current_user
from app.extensions import db
from app.models.notification import Notification

notifications_bp = Blueprint('notifications', __name__)

@notifications_bp.route('/')
@login_required
def index():
    user_notifications = Notification.query.filter_by(user_id=current_user.id).order_by(Notification.created_at.desc()).all()
    return render_template('notifications/index.html', notifications=user_notifications)

@notifications_bp.route('/read-all', methods=['POST'])
@login_required
def read_all():
    Notification.query.filter_by(user_id=current_user.id, is_read=False).update({'is_read': True})
    db.session.commit()
    flash('All notifications marked as read.', 'info')
    return redirect(url_for('notifications.index'))

@notifications_bp.route('/<int:notification_id>/read')
@login_required
def mark_read(notification_id):
    notif = Notification.query.get_or_404(notification_id)
    if notif.user_id != current_user.id:
        return redirect(url_for('notifications.index'))

    notif.is_read = True
    db.session.commit()

    if notif.link:
        return redirect(notif.link)
    return redirect(url_for('notifications.index'))
