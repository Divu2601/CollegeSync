from datetime import datetime, date, timedelta
from flask import Blueprint, render_template, request, redirect, url_for, flash, abort, jsonify
from flask_login import login_required, current_user
from sqlalchemy import func
from app.extensions import db
from app.utils import admin_required
from app.models.resource import Resource, ResourceCategory, ResourceBlock
from app.models.equipment import Equipment, EquipmentRequest
from app.models.department import Department
from app.models.society import Society
from app.models.user import User
from app.models.event import Event
from app.models.booking import BookingRequest, BookingResource, ApprovalHistory, SystemSetting
from app.services.approval_service import ApprovalService
from app.services.availability_service import AvailabilityService
from app.services.equipment_service import EquipmentService
from app.services.booking_service import BookingService

admin_bp = Blueprint('admin', __name__)

@admin_bp.before_request
@login_required
@admin_required
def require_admin():
    pass

@admin_bp.route('/')
@admin_bp.route('/dashboard')
def dashboard():
    total_resources = Resource.query.count()
    pending_count = BookingRequest.query.filter_by(status=BookingRequest.STATUS_PENDING).count()
    approved_count = BookingRequest.query.filter_by(status=BookingRequest.STATUS_APPROVED).count()
    total_users = User.query.count()

    upcoming_events = Event.query.join(BookingRequest).filter(
        BookingRequest.status == BookingRequest.STATUS_APPROVED,
        Event.event_date >= date.today()
    ).order_by(Event.event_date.asc()).limit(5).all()

    pending_bookings = BookingRequest.query.filter_by(status=BookingRequest.STATUS_PENDING).order_by(BookingRequest.submitted_at.asc()).limit(10).all()

    # Active maintenance
    active_maintenance = ResourceBlock.query.filter(ResourceBlock.end_at >= datetime.utcnow()).count()

    return render_template('admin/dashboard.html',
                           total_resources=total_resources,
                           pending_count=pending_count,
                           approved_count=approved_count,
                           total_users=total_users,
                           upcoming_events=upcoming_events,
                           pending_bookings=pending_bookings,
                           active_maintenance=active_maintenance)

@admin_bp.route('/bookings')
def bookings():
    status = request.args.get('status', '').strip().upper()
    search = request.args.get('search', '').strip()
    query = BookingRequest.query.join(Event).join(User, BookingRequest.requester_id == User.id)

    if status and status in BookingRequest.STATUSES:
        query = query.filter(BookingRequest.status == status)

    if search:
        query = query.filter(
            (Event.title.ilike(f"%{search}%")) |
            (User.name.ilike(f"%{search}%")) |
            (User.email.ilike(f"%{search}%"))
        )

    bookings_list = query.order_by(BookingRequest.submitted_at.desc()).all()

    return render_template('admin/bookings.html',
                           bookings=bookings_list,
                           selected_status=status,
                           search=search)

@admin_bp.route('/bookings/<int:booking_id>')
def booking_detail(booking_id):
    booking = BookingRequest.query.get_or_404(booking_id)

    # Perform real-time conflict analysis for administrator inspection
    conflict_analysis = []
    has_conflicts = False

    for br in booking.booking_resources:
        # Check maintenance conflict
        has_block, block_msg = AvailabilityService.check_maintenance_conflict(br.resource_id, br.start_at, br.end_at)
        # Check approved booking conflict
        has_collision, col_msg = AvailabilityService.check_booking_conflict(
            br.resource_id, br.start_at, br.end_at, exclude_booking_id=booking.id
        )

        item = {
            'resource_name': br.resource.name,
            'slot': f"{br.start_at.strftime('%d %b %Y, %H:%M')} - {br.end_at.strftime('%H:%M')}",
            'status': 'Clean' if not (has_block or has_collision) else 'Conflict',
            'details': block_msg or col_msg or 'Slot is available'
        }
        if has_block or has_collision:
            has_conflicts = True
        conflict_analysis.append(item)

    # Equipment check
    equipment_analysis = []
    for er in booking.equipment_requests:
        is_avail, avail_qty, msg = EquipmentService.check_equipment_availability(
            er.equipment_id, er.quantity, er.start_at, er.end_at, exclude_booking_id=booking.id
        )
        equipment_analysis.append({
            'name': er.equipment.name,
            'requested': er.quantity,
            'available': avail_qty,
            'status': 'Sufficient' if is_avail else 'Insufficient',
            'details': msg or f"{avail_qty} in stock for this slot"
        })
        if not is_avail:
            has_conflicts = True

    return render_template('admin/booking_detail.html',
                           booking=booking,
                           conflict_analysis=conflict_analysis,
                           equipment_analysis=equipment_analysis,
                           has_conflicts=has_conflicts)

@admin_bp.route('/bookings/<int:booking_id>/approve', methods=['POST'])
def approve_booking(booking_id):
    remarks = request.form.get('remarks', '').strip()
    success, message = ApprovalService.approve_booking(booking_id, current_user, remarks)
    if success:
        flash(f'Booking #{booking_id} has been approved successfully.', 'success')
    else:
        flash(f'Cannot approve booking #{booking_id}: {message}', 'danger')

    return redirect(url_for('admin.booking_detail', booking_id=booking_id))

@admin_bp.route('/bookings/<int:booking_id>/reject', methods=['POST'])
def reject_booking(booking_id):
    reason = request.form.get('rejection_reason', '').strip()
    if not reason:
        flash('A rejection reason must be provided.', 'warning')
        return redirect(url_for('admin.booking_detail', booking_id=booking_id))

    success, message = ApprovalService.reject_booking(booking_id, current_user, reason)
    if success:
        flash(f'Booking #{booking_id} was rejected.', 'info')
    else:
        flash(f'Failed to reject booking: {message}', 'danger')

    return redirect(url_for('admin.booking_detail', booking_id=booking_id))

@admin_bp.route('/bookings/<int:booking_id>/cancel', methods=['POST'])
def cancel_booking(booking_id):
    reason = request.form.get('reason', '').strip() or "Cancelled by administrator"
    success, message = BookingService.cancel_booking(booking_id, current_user, reason)
    if success:
        flash(f'Booking #{booking_id} has been cancelled.', 'info')
    else:
        flash(f'Failed to cancel booking: {message}', 'danger')

    return redirect(url_for('admin.booking_detail', booking_id=booking_id))

# --- Resource Management ---
@admin_bp.route('/resources')
def resources():
    resources_list = Resource.query.order_by(Resource.category_id, Resource.name).all()
    categories = ResourceCategory.query.order_by(ResourceCategory.name).all()
    return render_template('admin/resources.html', resources=resources_list, categories=categories)

@admin_bp.route('/resources/new', methods=['GET', 'POST'])
def resource_new():
    categories = ResourceCategory.query.order_by(ResourceCategory.name).all()
    departments = Department.query.order_by(Department.name).all()

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        category_id = request.form.get('category_id', type=int)
        capacity = request.form.get('capacity', type=int)
        location = request.form.get('location', '').strip()
        op_start = request.form.get('operating_hours_start', '09:00').strip()
        op_end = request.form.get('operating_hours_end', '17:00').strip()
        status = request.form.get('status', 'active')
        booking_allowed = bool(request.form.get('booking_allowed'))
        approval_required = bool(request.form.get('approval_required'))
        dept_id = request.form.get('department_id', type=int)
        eq_available = request.form.get('equipment_available', '').strip()
        instructions = request.form.get('special_instructions', '').strip()

        if not name or not category_id or not capacity or capacity <= 0:
            flash('Please specify a valid resource name, category, and positive capacity.', 'danger')
            return render_template('admin/resource_form.html', categories=categories, departments=departments, resource=None)

        if Resource.query.filter_by(name=name).first():
            flash(f'A resource named "{name}" already exists.', 'danger')
            return render_template('admin/resource_form.html', categories=categories, departments=departments, resource=None)

        res = Resource(
            name=name,
            category_id=category_id,
            capacity=capacity,
            location=location,
            operating_hours_start=op_start,
            operating_hours_end=op_end,
            status=status,
            booking_allowed=booking_allowed,
            approval_required=approval_required,
            department_id=dept_id if dept_id else None,
            equipment_available=eq_available,
            special_instructions=instructions
        )
        db.session.add(res)
        db.session.commit()
        flash(f'Resource "{name}" added successfully.', 'success')
        return redirect(url_for('admin.resources'))

    return render_template('admin/resource_form.html', categories=categories, departments=departments, resource=None)

@admin_bp.route('/resources/<int:resource_id>/edit', methods=['GET', 'POST'])
def resource_edit(resource_id):
    resource = Resource.query.get_or_404(resource_id)
    categories = ResourceCategory.query.order_by(ResourceCategory.name).all()
    departments = Department.query.order_by(Department.name).all()

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        category_id = request.form.get('category_id', type=int)
        capacity = request.form.get('capacity', type=int)

        if not name or not category_id or not capacity or capacity <= 0:
            flash('Please specify valid details.', 'danger')
            return render_template('admin/resource_form.html', categories=categories, departments=departments, resource=resource)

        existing = Resource.query.filter_by(name=name).first()
        if existing and existing.id != resource.id:
            flash('Another resource with this name already exists.', 'danger')
            return render_template('admin/resource_form.html', categories=categories, departments=departments, resource=resource)

        resource.name = name
        resource.category_id = category_id
        resource.capacity = capacity
        resource.location = request.form.get('location', '').strip()
        resource.operating_hours_start = request.form.get('operating_hours_start', '09:00').strip()
        resource.operating_hours_end = request.form.get('operating_hours_end', '17:00').strip()
        resource.status = request.form.get('status', 'active')
        resource.booking_allowed = bool(request.form.get('booking_allowed'))
        resource.approval_required = bool(request.form.get('approval_required'))
        dept_id = request.form.get('department_id', type=int)
        resource.department_id = dept_id if dept_id else None
        resource.equipment_available = request.form.get('equipment_available', '').strip()
        resource.special_instructions = request.form.get('special_instructions', '').strip()

        db.session.commit()
        flash(f'Resource "{resource.name}" updated successfully.', 'success')
        return redirect(url_for('admin.resources'))

    return render_template('admin/resource_form.html', categories=categories, departments=departments, resource=resource)

# --- Equipment Management ---
@admin_bp.route('/equipment')
def equipment():
    equipment_list = Equipment.query.order_by(Equipment.category, Equipment.name).all()
    return render_template('admin/equipment.html', equipment_list=equipment_list)

@admin_bp.route('/equipment/new', methods=['GET', 'POST'])
def equipment_new():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        category = request.form.get('category', '').strip()
        total_qty = request.form.get('total_quantity', type=int)
        condition = request.form.get('condition', 'Good')
        location = request.form.get('storage_location', '').strip()
        status = request.form.get('maintenance_status', 'Active')
        is_avail = bool(request.form.get('is_available'))

        if not name or not category or total_qty is None or total_qty < 0:
            flash('Please provide valid equipment name, category, and quantity.', 'danger')
            return render_template('admin/equipment_form.html', equipment=None)

        if Equipment.query.filter_by(name=name).first():
            flash(f'Equipment "{name}" already exists.', 'danger')
            return render_template('admin/equipment_form.html', equipment=None)

        eq = Equipment(
            name=name, category=category, total_quantity=total_qty,
            condition=condition, storage_location=location,
            maintenance_status=status, is_available=is_avail
        )
        db.session.add(eq)
        db.session.commit()
        flash(f'Equipment "{name}" added successfully.', 'success')
        return redirect(url_for('admin.equipment'))

    return render_template('admin/equipment_form.html', equipment=None)

@admin_bp.route('/equipment/<int:equipment_id>/edit', methods=['GET', 'POST'])
def equipment_edit(equipment_id):
    eq = Equipment.query.get_or_404(equipment_id)
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        category = request.form.get('category', '').strip()
        total_qty = request.form.get('total_quantity', type=int)

        if not name or not category or total_qty is None or total_qty < 0:
            flash('Invalid inputs.', 'danger')
            return render_template('admin/equipment_form.html', equipment=eq)

        existing = Equipment.query.filter_by(name=name).first()
        if existing and existing.id != eq.id:
            flash('Equipment with this name already exists.', 'danger')
            return render_template('admin/equipment_form.html', equipment=eq)

        eq.name = name
        eq.category = category
        eq.total_quantity = total_qty
        eq.condition = request.form.get('condition', 'Good')
        eq.storage_location = request.form.get('storage_location', '').strip()
        eq.maintenance_status = request.form.get('maintenance_status', 'Active')
        eq.is_available = bool(request.form.get('is_available'))

        db.session.commit()
        flash(f'Equipment "{eq.name}" updated successfully.', 'success')
        return redirect(url_for('admin.equipment'))

    return render_template('admin/equipment_form.html', equipment=eq)

# --- Maintenance Management ---
@admin_bp.route('/maintenance', methods=['GET', 'POST'])
def maintenance():
    resources = Resource.query.order_by(Resource.name).all()

    if request.method == 'POST':
        res_id = request.form.get('resource_id', type=int)
        s_str = request.form.get('start_at', '').strip()
        e_str = request.form.get('end_at', '').strip()
        reason = request.form.get('reason', '').strip()

        if not res_id or not s_str or not e_str or not reason:
            flash('Please fill in all maintenance block fields.', 'danger')
        else:
            try:
                s_dt = datetime.fromisoformat(s_str)
                e_dt = datetime.fromisoformat(e_str)
                if e_dt <= s_dt:
                    flash('End time must be after start time.', 'danger')
                else:
                    block = ResourceBlock(
                        resource_id=res_id,
                        start_at=s_dt,
                        end_at=e_dt,
                        reason=reason,
                        created_by_id=current_user.id
                    )
                    db.session.add(block)
                    db.session.commit()
                    flash('Maintenance blackout period scheduled successfully.', 'success')
            except Exception as e:
                flash(f'Failed to schedule maintenance: {str(e)}', 'danger')

        return redirect(url_for('admin.maintenance'))

    blocks = ResourceBlock.query.order_by(ResourceBlock.start_at.desc()).all()
    return render_template('admin/maintenance.html', blocks=blocks, resources=resources)

@admin_bp.route('/maintenance/<int:block_id>/delete', methods=['POST'])
def maintenance_delete(block_id):
    block = ResourceBlock.query.get_or_404(block_id)
    db.session.delete(block)
    db.session.commit()
    flash('Maintenance block removed.', 'info')
    return redirect(url_for('admin.maintenance'))

# --- User Management ---
@admin_bp.route('/users')
def users():
    users_list = User.query.order_by(User.name).all()
    return render_template('admin/users.html', users=users_list, roles=User.ROLES)

@admin_bp.route('/users/<int:user_id>/update-role', methods=['POST'])
def user_update_role(user_id):
    user = User.query.get_or_404(user_id)
    new_role = request.form.get('role', '').strip()
    is_active = bool(request.form.get('is_active'))

    if new_role in User.ROLES:
        user.role = new_role
    user.is_active = is_active
    db.session.commit()
    flash(f'User "{user.name}" updated successfully.', 'success')
    return redirect(url_for('admin.users'))

# --- Reports & Analytics ---
@admin_bp.route('/reports')
def reports():
    total_bookings = BookingRequest.query.count()
    approved = BookingRequest.query.filter_by(status=BookingRequest.STATUS_APPROVED).count()
    rejected = BookingRequest.query.filter_by(status=BookingRequest.STATUS_REJECTED).count()
    cancelled = BookingRequest.query.filter_by(status=BookingRequest.STATUS_CANCELLED).count()

    # Most booked resources
    top_resources = db.session.query(
        Resource.name,
        func.count(BookingResource.id).label('booking_count')
    ).join(BookingResource, Resource.id == BookingResource.resource_id)\
     .join(BookingRequest, BookingResource.booking_id == BookingRequest.id)\
     .filter(BookingRequest.status == BookingRequest.STATUS_APPROVED)\
     .group_by(Resource.name)\
     .order_by(func.count(BookingResource.id).desc())\
     .limit(5).all()

    # Department-wise bookings
    dept_stats = db.session.query(
        Department.name,
        func.count(Event.id).label('event_count')
    ).join(Event, Department.id == Event.department_id)\
     .join(BookingRequest, Event.id == BookingRequest.event_id)\
     .filter(BookingRequest.status == BookingRequest.STATUS_APPROVED)\
     .group_by(Department.name)\
     .order_by(func.count(Event.id).desc()).all()

    # Society-wise bookings
    soc_stats = db.session.query(
        Society.name,
        func.count(Event.id).label('event_count')
    ).join(Event, Society.id == Event.society_id)\
     .join(BookingRequest, Event.id == BookingRequest.event_id)\
     .filter(BookingRequest.status == BookingRequest.STATUS_APPROVED)\
     .group_by(Society.name)\
     .order_by(func.count(Event.id).desc()).all()

    return render_template('admin/reports.html',
                           total_bookings=total_bookings,
                           approved=approved,
                           rejected=rejected,
                           cancelled=cancelled,
                           top_resources=top_resources,
                           dept_stats=dept_stats,
                           soc_stats=soc_stats)

# --- System Settings ---
@admin_bp.route('/settings', methods=['GET', 'POST'])
def settings():
    if request.method == 'POST':
        for key in request.form:
            if key != 'csrf_token':
                SystemSetting.set_value(key, request.form[key])
        flash('College operational settings updated.', 'success')
        return redirect(url_for('admin.settings'))

    all_settings = SystemSetting.query.order_by(SystemSetting.key).all()
    return render_template('admin/settings.html', settings=all_settings)
