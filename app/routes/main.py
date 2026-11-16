from datetime import datetime, date
from flask import Blueprint, render_template, redirect, url_for
from flask_login import current_user, login_required
from app.models.resource import Resource, ResourceCategory
from app.models.event import Event
from app.models.booking import BookingRequest, BookingResource
from app.models.equipment import Equipment

main_bp = Blueprint('main', __name__)

@main_bp.route('/')
def index():
    if current_user.is_authenticated:
        if current_user.is_admin():
            return redirect(url_for('admin.dashboard'))
        return redirect(url_for('main.dashboard'))
    return redirect(url_for('auth.login'))

@main_bp.route('/dashboard')
@login_required
def dashboard():
    # User's recent bookings
    my_bookings = BookingRequest.query.filter_by(requester_id=current_user.id).order_by(BookingRequest.submitted_at.desc()).limit(5).all()
    
    # Counts
    pending_count = BookingRequest.query.filter_by(requester_id=current_user.id, status=BookingRequest.STATUS_PENDING).count()
    approved_count = BookingRequest.query.filter_by(requester_id=current_user.id, status=BookingRequest.STATUS_APPROVED).count()
    
    # Upcoming confirmed college events
    upcoming_events = Event.query.join(BookingRequest).filter(
        BookingRequest.status == BookingRequest.STATUS_APPROVED,
        Event.event_date >= date.today()
    ).order_by(Event.event_date.asc(), Event.start_time.asc()).limit(5).all()

    return render_template('dashboard/index.html',
                           my_bookings=my_bookings,
                           pending_count=pending_count,
                           approved_count=approved_count,
                           upcoming_events=upcoming_events)

@main_bp.route('/calendar')
def calendar():
    categories = ResourceCategory.query.order_by(ResourceCategory.name).all()
    resources = Resource.query.filter_by(status='active').order_by(Resource.name).all()
    return render_template('calendar/index.html', categories=categories, resources=resources)
