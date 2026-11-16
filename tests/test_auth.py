import unittest
from app import create_app
from app.extensions import db
from app.models.user import User
from app.models.department import Department

class AuthTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app('testing')
        self.app_context = self.app.app_context()
        self.app_context.push()
        self.client = self.app.test_client()
        db.create_all()

        dept = Department(name="Computer Science", code="CS")
        db.session.add(dept)
        db.session.commit()

        # Admin user
        admin = User(name="Admin User", email="admin@test.du.ac.in", role="Administrator")
        admin.set_password("adminpass")
        db.session.add(admin)

        # Student user
        student = User(name="Student User", email="student@test.du.ac.in", role="Student")
        student.set_password("studentpass")
        db.session.add(student)

        # Inactive user
        inactive = User(name="Inactive User", email="inactive@test.du.ac.in", role="Student", is_active=False)
        inactive.set_password("inactivepass")
        db.session.add(inactive)

        db.session.commit()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def test_login_success(self):
        res = self.client.post('/auth/login', data={
            'email': 'admin@test.du.ac.in',
            'password': 'adminpass'
        }, follow_redirects=False)
        self.assertEqual(res.status_code, 302)
        self.assertIn('/admin', res.headers['Location'])

    def test_login_invalid_password(self):
        res = self.client.post('/auth/login', data={
            'email': 'admin@test.du.ac.in',
            'password': 'wrongpassword'
        }, follow_redirects=True)
        self.assertIn(b'Invalid email address or password', res.data)

    def test_inactive_user_cannot_login(self):
        res = self.client.post('/auth/login', data={
            'email': 'inactive@test.du.ac.in',
            'password': 'inactivepass'
        }, follow_redirects=True)
        self.assertIn(b'account has been deactivated', res.data)

    def test_student_cannot_access_admin_dashboard(self):
        # Login as student
        self.client.post('/auth/login', data={
            'email': 'student@test.du.ac.in',
            'password': 'studentpass'
        })
        # Attempt to access admin dashboard
        res = self.client.get('/admin/dashboard')
        self.assertEqual(res.status_code, 403)
        self.assertIn(b'Access Restricted', res.data)

    def test_admin_can_access_admin_dashboard(self):
        # Login as admin
        self.client.post('/auth/login', data={
            'email': 'admin@test.du.ac.in',
            'password': 'adminpass'
        })
        res = self.client.get('/admin/dashboard')
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'Administrator Control Center', res.data)

if __name__ == '__main__':
    unittest.main()
