from datetime import datetime, date
from flask import Blueprint, render_template, request, abort
from app.models.resource import Resource, ResourceCategory, ResourceBlock
from app.models.booking import BookingRequest, BookingResource

resources_bp = Blueprint('resources', __name__)

@resources_bp.route('/')
def index():
    category_id = request.args.get('category_id', type=int)
    search_q = request.args.get('q', '').strip()
    min_capacity = request.args.get('min_capacity', type=int)
    status = request.args.get('status', '').strip()

    query = Resource.query

    if category_id:
        query = query.filter(Resource.category_id == category_id)

    if search_q:
        query = query.filter(
            (Resource.name.ilike(f"%{search_q}%")) |
            (Resource.location.ilike(f"%{search_q}%")) |
            (Resource.special_instructions.ilike(f"%{search_q}%"))
        )

    if min_capacity:
        query = query.filter(Resource.capacity >= min_capacity)

    if status:
        query = query.filter(Resource.status == status)

    resources = query.order_by(Resource.name).all()
    categories = ResourceCategory.query.order_by(ResourceCategory.name).all()

    return render_template('resources/index.html',
                           resources=resources,
                           categories=categories,
                           selected_category=category_id,
                           search_q=search_q,
                           min_capacity=min_capacity,
                           selected_status=status)

@resources_bp.route('/<int:resource_id>')
def detail(resource_id):
    resource = Resource.query.get_or_404(resource_id)

    # Upcoming bookings for this resource
    upcoming_bookings = BookingResource.query.join(BookingRequest).filter(
        BookingResource.resource_id == resource.id,
        BookingRequest.status == BookingRequest.STATUS_APPROVED,
        BookingResource.end_at >= datetime.utcnow()
    ).order_by(BookingResource.start_at.asc()).limit(10).all()

    # Maintenance blocks
    upcoming_blocks = ResourceBlock.query.filter(
        ResourceBlock.resource_id == resource.id,
        ResourceBlock.end_at >= datetime.utcnow()
    ).order_by(ResourceBlock.start_at.asc()).all()

    return render_template('resources/detail.html',
                           resource=resource,
                           upcoming_bookings=upcoming_bookings,
                           upcoming_blocks=upcoming_blocks)
