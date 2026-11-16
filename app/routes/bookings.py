from datetime import datetime, date, time
from flask import Blueprint, render_template, request, redirect, url_for, flash, abort, jsonify
from flask_login import login_required, current_user
from app.models.resource import Resource, ResourceCategory
from app.models.equipment import Equipment
from app.models.department import Department
from app.models.society import Society
from app.models.event import Event
from app.models.booking import BookingRequest, BookingResource
from app.services.booking_service import BookingService
from app.services.availability_service import AvailabilityService
from app.services.equipment_service import EquipmentService

bookings_bp = Blueprint('bookings', __name__)

@bookings_bp.route('/')
@login_required
def index():
    status_filter = request.args.get('status', '').strip().upper()
    query = BookingRequest.query.filter_by(requester_id=current_user.id)

    if status_filter in BookingRequest.STATUSES:
        query = query.filter_by(status=status_filter)

    bookings = query.order_by(BookingRequest.submitted_at.desc()).all()

    return render_template('bookings/my_bookings.html',
                           bookings=bookings,
                           selected_status=status_filter)

@bookings_bp.route('/new', methods=['GET', 'POST'])
@login_required
def create():
    if not current_user.can_request():
        flash('Your account is currently inactive and cannot submit booking requests.', 'danger')
        return redirect(url_for('main.dashboard'))

    resources = Resource.query.filter_by(status='active', booking_allowed=True).order_by(Resource.name).all()
    categories = ResourceCategory.query.order_by(ResourceCategory.name).all()
    equipments = Equipment.query.filter_by(is_available=True, maintenance_status='Active').order_by(Equipment.name).all()
    departments = Department.query.order_by(Department.name).all()
    societies = Society.query.order_by(Society.name).all()

    if request.method == 'POST':
        # 1. Parse Event Details
        title = request.form.get('title', '').strip()
        description = request.form.get('description', '').strip()
        category = request.form.get('category', 'Academic')
        expected_attendance = request.form.get('expected_attendance', type=int)
        event_date_str = request.form.get('event_date', '')
        start_time_str = request.form.get('start_time', '')
        end_time_str = request.form.get('end_time', '')
        dept_id = request.form.get('department_id', type=int)
        soc_id = request.form.get('society_id', type=int)
        requirements = request.form.get('requirements', '').strip()

        if not title or not description or not event_date_str or not start_time_str or not end_time_str:
            flash('Please fill in all required event details.', 'danger')
            return render_template('bookings/create.html',
                                   resources=resources, categories=categories,
                                   equipments=equipments, departments=departments, societies=societies)

        try:
            event_date = datetime.strptime(event_date_str, '%Y-%m-%d').date()
            start_parts = [int(p) for p in start_time_str.split(':')]
            end_parts = [int(p) for p in end_time_str.split(':')]
            start_time = time(start_parts[0], start_parts[1])
            end_time = time(end_parts[0], end_parts[1])
        except Exception:
            flash('Invalid date or time format provided.', 'danger')
            return render_template('bookings/create.html',
                                   resources=resources, categories=categories,
                                   equipments=equipments, departments=departments, societies=societies)

        if end_time <= start_time:
            flash('Event end time must be after start time.', 'danger')
            return render_template('bookings/create.html',
                                   resources=resources, categories=categories,
                                   equipments=equipments, departments=departments, societies=societies)

        # 2. Parse Multiple Resources and Time Intervals
        # Form inputs: resource_ids[], resource_start_times[], resource_end_times[]
        res_ids = request.form.getlist('resource_ids[]')
        res_start_times = request.form.getlist('resource_start_times[]')
        res_end_times = request.form.getlist('resource_end_times[]')

        if not res_ids:
            flash('You must select at least one infrastructure resource to book.', 'warning')
            return render_template('bookings/create.html',
                                   resources=resources, categories=categories,
                                   equipments=equipments, departments=departments, societies=societies)

        resource_slots = []
        for i, r_id_str in enumerate(res_ids):
            try:
                r_id = int(r_id_str)
                # If resource-specific times were provided, use them; otherwise inherit event times
                r_start_str = res_start_times[i] if i < len(res_start_times) and res_start_times[i] else start_time_str
                r_end_str = res_end_times[i] if i < len(res_end_times) and res_end_times[i] else end_time_str

                s_p = [int(p) for p in r_start_str.split(':')]
                e_p = [int(p) for p in r_end_str.split(':')]
                slot_s = time(s_p[0], s_p[1])
                slot_e = time(e_p[0], e_p[1])

                if slot_e <= slot_s:
                    flash(f'Slot end time must be after start time for all selected resources.', 'danger')
                    return render_template('bookings/create.html',
                                           resources=resources, categories=categories,
                                           equipments=equipments, departments=departments, societies=societies)

                resource_slots.append({
                    'resource_id': r_id,
                    'start_at': datetime.combine(event_date, slot_s),
                    'end_at': datetime.combine(event_date, slot_e)
                })
            except (ValueError, IndexError):
                continue

        if not resource_slots:
            flash('No valid resources selected.', 'danger')
            return render_template('bookings/create.html',
                                   resources=resources, categories=categories,
                                   equipments=equipments, departments=departments, societies=societies)

        # 3. Parse Equipment Requirements
        eq_ids = request.form.getlist('equipment_ids[]')
        eq_qtys = request.form.getlist('equipment_quantities[]')
        equipment_items = []
        for i, eq_id_str in enumerate(eq_ids):
            if not eq_id_str:
                continue
            try:
                eq_id = int(eq_id_str)
                qty = int(eq_qtys[i]) if i < len(eq_qtys) and eq_qtys[i] else 1
                if qty > 0:
                    equipment_items.append({
                        'equipment_id': eq_id,
                        'quantity': qty,
                        'start_at': datetime.combine(event_date, start_time),
                        'end_at': datetime.combine(event_date, end_time)
                    })
            except (ValueError, IndexError):
                continue

        # 4. Invoke Booking Service
        event_data = {
            'title': title,
            'description': description,
            'category': category,
            'expected_attendance': expected_attendance or 50,
            'event_date': event_date,
            'start_time': start_time,
            'end_time': end_time,
            'department_id': dept_id if dept_id else None,
            'society_id': soc_id if soc_id else None,
            'requirements': requirements
        }

        success, result = BookingService.create_event_booking(
            requester=current_user,
            event_data=event_data,
            resource_slots=resource_slots,
            equipment_items=equipment_items
        )

        if not success:
            flash(f'Booking request failed: {result}', 'danger')
            return render_template('bookings/create.html',
                                   resources=resources, categories=categories,
                                   equipments=equipments, departments=departments, societies=societies)

        flash(f'Your booking request for "{title}" has been submitted successfully and is awaiting admin approval!', 'success')
        return redirect(url_for('bookings.detail', booking_id=result.id))

    # Pre-select resource if requested via query param
    preselected_resource_id = request.args.get('resource_id', type=int)

    return render_template('bookings/create.html',
                           resources=resources,
                           categories=categories,
                           equipments=equipments,
                           departments=departments,
                           societies=societies,
                           preselected_resource_id=preselected_resource_id)

@bookings_bp.route('/<int:booking_id>')
@login_required
def detail(booking_id):
    booking = BookingRequest.query.get_or_404(booking_id)

    # Security check: requesters can only view their own bookings unless admin
    if not current_user.is_admin() and booking.requester_id != current_user.id:
        abort(403, description="You are not authorized to view this booking request.")

    return render_template('bookings/detail.html', booking=booking)

@bookings_bp.route('/<int:booking_id>/cancel', methods=['POST'])
@login_required
def cancel(booking_id):
    booking = BookingRequest.query.get_or_404(booking_id)

    if not current_user.is_admin() and booking.requester_id != current_user.id:
        abort(403, description="You cannot cancel this booking.")

    reason = request.form.get('reason', '').strip()
    if not reason:
        reason = "Cancelled by requester."

    success, message = BookingService.cancel_booking(booking_id, current_user, reason)
    if success:
        flash(message, 'info')
    else:
        flash(message, 'danger')

    return redirect(url_for('bookings.detail', booking_id=booking_id))
