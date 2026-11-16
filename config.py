import os

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
INSTANCE_DIR = os.path.join(BASE_DIR, 'instance')
os.makedirs(INSTANCE_DIR, exist_ok=True)

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'campusbook-pgdav-secure-secret-key-2026')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # College default operational configurations
    DEFAULT_OPERATING_START = "09:00"
    DEFAULT_OPERATING_END = "17:00"
    MAX_ADVANCE_BOOKING_DAYS = int(os.environ.get('MAX_ADVANCE_BOOKING_DAYS', 30))
    ALLOW_SAME_DAY_BOOKING = os.environ.get('ALLOW_SAME_DAY_BOOKING', 'true').lower() == 'true'
    HOLD_PENDING_REQUESTS = os.environ.get('HOLD_PENDING_REQUESTS', 'false').lower() == 'true'

class DevelopmentConfig(Config):
    DEBUG = True
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        'DATABASE_URL', 
        f"sqlite:///{os.path.join(INSTANCE_DIR, 'campusbook.db')}"
    )

class TestingConfig(Config):
    TESTING = True
    WTF_CSRF_ENABLED = False
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'

class ProductionConfig(Config):
    DEBUG = False
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL')

config_by_name = {
    'development': DevelopmentConfig,
    'testing': TestingConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}
