import os
from app import create_app
from seed import seed_database

config_name = os.environ.get('FLASK_CONFIG', 'development')
app = create_app(config_name)

if __name__ == '__main__':
    # Auto-seed on first run if database is empty
    with app.app_context():
        from app.models.resource import Resource
        try:
            if Resource.query.count() == 0:
                print("Database is empty. Running initial seeding...")
                seed_database()
        except Exception:
            print("Initializing database...")
            seed_database()

    port = int(os.environ.get('PORT', 5000))
    print(f"Starting CampusBook on http://127.0.0.1:{port}")
    app.run(host='127.0.0.1', port=port, debug=True)

