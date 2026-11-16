import secrets
from functools import wraps
from flask import session, request, abort, current_app
from flask_login import current_user

def generate_csrf_token():
    if '_csrf_token' not in session:
        session['_csrf_token'] = secrets.token_hex(32)
    return session['_csrf_token']

def validate_csrf():
    if not current_app.config.get('WTF_CSRF_ENABLED', True):
        return
    if request.method in ('POST', 'PUT', 'PATCH', 'DELETE'):
        token = request.form.get('csrf_token') or request.headers.get('X-CSRFToken')
        expected_token = session.get('_csrf_token')
        if not expected_token or not token or not secrets.compare_digest(token, expected_token):
            abort(400, description="Invalid or missing CSRF token. Please refresh and try again.")

def role_required(*allowed_roles):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                return current_app.login_manager.unauthorized()
            if not current_user.is_active:
                abort(403, description="Your account has been deactivated. Please contact an administrator.")
            if current_user.role not in allowed_roles and current_user.role != 'Administrator':
                abort(403, description="You do not have permission to access this resource.")
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            return current_app.login_manager.unauthorized()
        if not current_user.is_active:
            abort(403, description="Your account has been deactivated.")
        if current_user.role != 'Administrator':
            abort(403, description="Administrator access required.")
        return f(*args, **kwargs)
    return decorated_function

def coordinator_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            return current_app.login_manager.unauthorized()
        if not current_user.is_active:
            abort(403, description="Your account has been deactivated.")
        allowed = {'Administrator', 'Society Coordinator', 'Department Coordinator', 'Faculty'}
        if current_user.role not in allowed:
            abort(403, description="Coordinator or Faculty permission required.")
        return f(*args, **kwargs)
    return decorated_function
