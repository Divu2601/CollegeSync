from datetime import datetime, date, timedelta
from flask import Blueprint, jsonify, request
from sqlalchemy import func
from app.extensions import db
from app.models.resource import Resource, ResourceCategory
from app.models.equipment import Equipment
from app.models.event import Event
from app.models.booking import BookingRequest, BookingResource
from app.models.department import Department
from app.models.society import Society
from app.services.availability_service import AvailabilityService
from app.services.equipment_service import EquipmentService

api_bp = Blueprint('api', __name__)

@api_bp.route('/calendar/events')
def calendar_events():
    """
    Returns events, bookings, and maintenance blackout intervals for FullCalendar.
    """
    start_str = request.args.get('start')
    end_str = request.args.get('end')
    resource_id = request.args.get('resource_id', type=int)
    category_id = request.args.get('category_id', type=int)

    # Defaults to current month if not provided
    if not start_str:
        start_dt = datetime.utcnow() - timedelta(days=30)
    else:
        try:
            start_dt = datetime.fromisoformat(start_str.replace('Z', '+00:00'))
        except Exception:
            start_dt = datetime.utcnow() - timedelta(days=30)

    if not end_str:
        end_dt = datetime.utcnow() + timedelta(days=60)
    else:
        try:
            end_dt = datetime.fromisoformat(end_str.replace('Z', '+00:00'))
        except Exception:
            end_dt = datetime.utcnow() + timedelta(days=60)

    events = AvailabilityService.get_calendar_events(
        start_dt=start_dt,
        end_dt=end_dt,
        resource_id=resource_id,
        category_id=category_id
    )

    return jsonify(events)

@api_bp.route('/resources')
def get_resources():
    category_id = request.args.get('category_id', type=int)
    query = Resource.query.filter_by(status='active')
    if category_id:
        query = query.filter_by(category_id=category_id)
    resources = query.order_by(Resource.name).all()
    return jsonify([r.to_dict() for r in resources])

@api_bp.route('/resources/<int:resource_id>')
def get_resource(resource_id):
    resource = Resource.query.get_or_404(resource_id)
    return jsonify(resource.to_dict())

@api_bp.route('/resources/<int:resource_id>/availability')
def check_availability(resource_id):
    start_str = request.args.get('start')
    end_str = request.args.get('end')

    if not start_str or not end_str:
        return jsonify({'error': 'start and end parameters are required'}), 400

    try:
        start_dt = datetime.fromisoformat(start_str)
        end_dt = datetime.fromisoformat(end_str)
    except ValueError:
        return jsonify({'error': 'Invalid datetime format. Use ISO format (YYYY-MM-DDTHH:MM:SS)'}), 400

    is_avail, reason = AvailabilityService.is_resource_available(resource_id, start_dt, end_dt)
    return jsonify({
        'resource_id': resource_id,
        'available': is_avail,
        'message': reason
    })

@api_bp.route('/equipment/availability')
def check_equipment_availability():
    equipment_id = request.args.get('equipment_id', type=int)
    qty = request.args.get('quantity', 1, type=int)
    start_str = request.args.get('start')
    end_str = request.args.get('end')

    if not equipment_id or not start_str or not end_str:
        return jsonify({'error': 'equipment_id, start, and end parameters are required'}), 400

    try:
        start_dt = datetime.fromisoformat(start_str)
        end_dt = datetime.fromisoformat(end_str)
    except ValueError:
        return jsonify({'error': 'Invalid ISO datetime'}), 400

    is_avail, avail_qty, msg = EquipmentService.check_equipment_availability(equipment_id, qty, start_dt, end_dt)
    return jsonify({
        'equipment_id': equipment_id,
        'requested_quantity': qty,
        'available_quantity': avail_qty,
        'available': is_avail,
        'message': msg
    })

@api_bp.route('/reports/charts')
def chart_data():
    """Returns analytics data formatted for Chart.js"""
    # 1. Booking Status Distribution
    status_counts = db.session.query(
        BookingRequest.status,
        func.count(BookingRequest.id)
    ).group_by(BookingRequest.status).all()

    # 2. Resource Utilisation
    resource_bookings = db.session.query(
        Resource.name,
        func.count(BookingResource.id)
    ).join(BookingResource, Resource.id == BookingResource.resource_id)\
     .join(BookingRequest, BookingResource.booking_id == BookingRequest.id)\
     .filter(BookingRequest.status == BookingRequest.STATUS_APPROVED)\
     .group_by(Resource.name)\
     .order_by(func.count(BookingResource.id).desc())\
     .limit(8).all()

    # 3. Department distribution
    dept_events = db.session.query(
        Department.name,
        func.count(Event.id)
    ).join(Event, Department.id == Event.department_id)\
     .group_by(Department.name).all()

    return jsonify({
        'status': {
            'labels': [s[0] for s in status_counts],
            'values': [s[1] for s in status_counts]
        },
        'resources': {
            'labels': [r[0] for r in resource_bookings],
            'values': [r[1] for r in resource_bookings]
        },
        'departments': {
            'labels': [d[0] for d in dept_events],
            'values': [d[1] for d in dept_events]
        }
    })
