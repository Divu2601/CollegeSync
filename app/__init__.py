from datetime import datetime
from flask import Flask, render_template, request, session, abort
from config import config_by_name
from app.extensions import db, login_manager
from app.utils import generate_csrf_token, validate_csrf

def create_app(config_name='development'):
    app = Flask(__name__)
    app.config.from_object(config_by_name.get(config_name, config_by_name['default']))

    # Initialize extensions
    db.init_app(app)
    login_manager.init_app(app)

    # CSRF and global template context
    @app.before_request
    def before_request_handler():
        # Exclude specific non-CSRF or testing paths if needed
        if request.endpoint and request.endpoint.startswith('api.'):
            # API can either use CSRF or token; allow GET / safe methods
            if request.method in ('GET', 'HEAD', 'OPTIONS'):
                return
            # If Content-Type is json and API call, allow X-CSRFToken or header, or validate
            token = request.headers.get('X-CSRFToken') or request.form.get('csrf_token')
            expected = session.get('_csrf_token')
            if expected and token and token == expected:
                return
            # If not in browser session (direct API call), allow or check
        validate_csrf()

    @app.context_processor
    def inject_global_utilities():
        from flask_login import current_user
        from app.models.notification import Notification

        unread_count = 0
        if current_user.is_authenticated:
            try:
                unread_count = Notification.query.filter_by(user_id=current_user.id, is_read=False).count()
            except Exception:
                unread_count = 0

        return {
            'csrf_token': generate_csrf_token,
            'now': datetime.utcnow(),
            'unread_notifications_count': unread_count,
            'current_year': datetime.utcnow().year
        }

    # Template filters
    @app.template_filter('datetime_format')
    def datetime_format_filter(value, format='%d %b %Y, %I:%M %p'):
        if value is None:
            return ""
        if isinstance(value, str):
            try:
                value = datetime.fromisoformat(value)
            except Exception:
                return value
        return value.strftime(format)

    @app.template_filter('date_format')
    def date_format_filter(value, format='%d %b %Y'):
        if value is None:
            return ""
        return value.strftime(format)

    @app.template_filter('time_format')
    def time_format_filter(value, format='%I:%M %p'):
        if value is None:
            return ""
        return value.strftime(format)

    # Register blueprints
    from app.routes.main import main_bp
    from app.routes.auth import auth_bp
    from app.routes.resources import resources_bp
    from app.routes.bookings import bookings_bp
    from app.routes.admin import admin_bp
    from app.routes.api import api_bp
    from app.routes.notifications import notifications_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(resources_bp, url_prefix='/resources')
    app.register_blueprint(bookings_bp, url_prefix='/bookings')
    app.register_blueprint(admin_bp, url_prefix='/admin')
    app.register_blueprint(api_bp, url_prefix='/api')
    app.register_blueprint(notifications_bp, url_prefix='/notifications')

    # Error handlers
    @app.errorhandler(400)
    def bad_request_error(e):
        return render_template('errors/400.html', error=e), 400

    @app.errorhandler(403)
    def forbidden_error(e):
        return render_template('errors/403.html', error=e), 403

    @app.errorhandler(404)
    def not_found_error(e):
        return render_template('errors/404.html', error=e), 404

    @app.errorhandler(500)
    def internal_error(e):
        db.session.rollback()
        return render_template('errors/500.html', error=e), 500

    return app
