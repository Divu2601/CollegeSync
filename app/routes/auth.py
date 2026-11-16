from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from app.extensions import db
from app.models.user import User
from app.models.department import Department
from app.models.society import Society, SocietyMembership

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        if current_user.is_admin():
            return redirect(url_for('admin.dashboard'))
        return redirect(url_for('main.dashboard'))

    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        remember = bool(request.form.get('remember'))

        user = User.query.filter_by(email=email).first()
        if not user or not user.check_password(password):
            flash('Invalid email address or password.', 'danger')
            return render_template('auth/login.html')

        if not user.is_active:
            flash('Your account has been deactivated. Please contact the administrator.', 'warning')
            return render_template('auth/login.html')

        login_user(user, remember=remember)
        flash(f'Welcome back, {user.name}!', 'success')
        next_page = request.args.get('next')
        if next_page and next_page.startswith('/'):
            return redirect(next_page)
        
        if user.is_admin():
            return redirect(url_for('admin.dashboard'))
        return redirect(url_for('main.dashboard'))

    return render_template('auth/login.html')

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))

    departments = Department.query.order_by(Department.name).all()
    societies = Society.query.order_by(Society.name).all()

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')
        role = request.form.get('role', 'Student')
        department_id = request.form.get('department_id')
        phone = request.form.get('phone', '').strip()
        society_ids = request.form.getlist('society_ids')

        # Allowed self-registration roles
        if role not in ['Student', 'Faculty', 'Staff', 'Society Coordinator']:
            role = 'Student'

        if not name or not email or not password:
            flash('Please complete all required fields.', 'warning')
            return render_template('auth/register.html', departments=departments, societies=societies)

        if password != confirm_password:
            flash('Passwords do not match.', 'danger')
            return render_template('auth/register.html', departments=departments, societies=societies)

        if User.query.filter_by(email=email).first():
            flash('An account with this email address already exists.', 'danger')
            return render_template('auth/register.html', departments=departments, societies=societies)

        user = User(
            name=name,
            email=email,
            role=role,
            department_id=int(department_id) if department_id else None,
            phone=phone,
            is_active=True
        )
        user.set_password(password)
        db.session.add(user)
        db.session.flush()

        for sid in society_ids:
            try:
                mem = SocietyMembership(
                    user_id=user.id,
                    society_id=int(sid),
                    membership_role='Coordinator' if role == 'Society Coordinator' else 'Member'
                )
                db.session.add(mem)
            except ValueError:
                pass

        db.session.commit()
        flash('Registration successful! You may now log in.', 'success')
        return redirect(url_for('auth.login'))

    return render_template('auth/register.html', departments=departments, societies=societies)

@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out safely.', 'info')
    return redirect(url_for('auth.login'))

@auth_bp.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    departments = Department.query.order_by(Department.name).all()
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        phone = request.form.get('phone', '').strip()
        department_id = request.form.get('department_id')
        new_password = request.form.get('new_password', '')

        if name:
            current_user.name = name
        current_user.phone = phone
        if department_id:
            current_user.department_id = int(department_id)

        if new_password:
            if len(new_password) < 6:
                flash('New password must be at least 6 characters.', 'warning')
                return render_template('auth/profile.html', departments=departments)
            current_user.set_password(new_password)
            flash('Password updated successfully.', 'success')

        db.session.commit()
        flash('Profile updated successfully.', 'success')
        return redirect(url_for('auth.profile'))

    return render_template('auth/profile.html', departments=departments)
