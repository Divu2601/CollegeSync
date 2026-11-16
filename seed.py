import os
import sys
from datetime import datetime, date, time, timedelta

# Ensure project root is in sys.path for direct script execution
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from app import create_app
from app.extensions import db
from app.models import (
    Department, Society, SocietyMembership, User,
    ResourceCategory, Resource, ResourceBlock,
    Equipment, EquipmentRequest,
    Event, BookingRequest, BookingResource, ApprovalHistory, SystemSetting
)

def seed_database(app=None):
    if app is None:
        app = create_app(os.environ.get('FLASK_CONFIG', 'development'))
    with app.app_context():
        print("Recreating database tables...")
        db.create_all()

        # 1. System Settings
        settings = [
            ('DEFAULT_OPERATING_START', '09:00', 'Default earliest booking hour'),
            ('DEFAULT_OPERATING_END', '17:00', 'Default latest booking hour'),
            ('MAX_ADVANCE_BOOKING_DAYS', '60', 'Maximum days in advance a resource can be booked'),
            ('ALLOW_SAME_DAY_BOOKING', 'true', 'Whether same-day bookings are allowed'),
            ('HOLD_PENDING_REQUESTS', 'false', 'Whether pending requests hold the slot prior to admin approval'),
            ('COLLEGE_NAME', 'PGDAV College (University of Delhi)', 'Institution Name')
        ]
        for key, val, desc in settings:
            if not SystemSetting.query.filter_by(key=key).first():
                db.session.add(SystemSetting(key=key, value=val, description=desc))
        db.session.commit()
        print("System settings seeded.")

        # 2. Departments (10 specified in requirements)
        dept_names = [
            ("Commerce", "COM", "Department of Commerce"),
            ("Sanskrit", "SKT", "Department of Sanskrit"),
            ("Hindi", "HIN", "Department of Hindi"),
            ("Mathematics", "MTH", "Department of Mathematics"),
            ("Computer Science", "CS", "Department of Computer Science"),
            ("Statistics", "STAT", "Department of Statistics"),
            ("English", "ENG", "Department of English"),
            ("History", "HIS", "Department of History"),
            ("Political Science", "POL", "Department of Political Science"),
            ("Economics", "ECO", "Department of Economics"),
        ]
        dept_map = {}
        for name, code, desc in dept_names:
            dept = Department.query.filter_by(name=name).first()
            if not dept:
                dept = Department(name=name, code=code, description=desc)
                db.session.add(dept)
                db.session.flush()
            dept_map[name] = dept
        db.session.commit()
        print(f"Seeded {len(dept_map)} Departments.")

        # 3. Societies
        societies_data = [
            ("Hyperion", "Cultural", "The Dramatics Society of PGDAV College"),
            ("Raaga", "Cultural", "The Music Society of PGDAV College"),
            ("Iris", "Cultural", "The Film & Photography Society"),
            ("TechSoc", "Technical", "The Computer Science and Technology Society"),
            ("Commercium", "Academic", "The Commerce Association"),
            ("Chanakya", "Academic", "The Economics Society"),
            ("Sports Board", "Sports", "PGDAV Sports & Athletics Committee")
        ]
        soc_map = {}
        for name, cat, desc in societies_data:
            soc = Society.query.filter_by(name=name).first()
            if not soc:
                soc = Society(name=name, category=cat, description=desc)
                db.session.add(soc)
                db.session.flush()
            soc_map[name] = soc
        db.session.commit()
        print(f"Seeded {len(soc_map)} Societies.")

        # 4. Resource Categories
        categories_data = [
            ("Seminar spaces", "Auditoriums and seminar halls with AV equipment"),
            ("Common rooms", "Recreational and common activity spaces"),
            ("Laboratories", "Specialized computing and practical science labs"),
            ("Sports facilities", "Indoor sports rooms and outdoor athletic grounds"),
            ("Departmental rooms", "Dedicated departmental meeting and academic rooms")
        ]
        cat_map = {}
        for name, desc in categories_data:
            cat = ResourceCategory.query.filter_by(name=name).first()
            if not cat:
                cat = ResourceCategory(name=name, description=desc)
                db.session.add(cat)
                db.session.flush()
            cat_map[name] = cat
        db.session.commit()
        print("Resource categories seeded.")

        # 5. The Exact 21 Infrastructure Resources
        # (2 Seminar + 2 Common rooms + 3 Labs + 4 Sports + 10 Departmental rooms = 21)
        resources_seed = [
            # Seminar Spaces (2)
            ("Old Seminar Hall", "Seminar spaces", 100, "Ground Floor, Admin Block", "09:00", "17:00", "Projector, Audio System, 100 Chairs", "Keep stage clear after use", None),
            ("New Seminar Hall", "Seminar spaces", 150, "Second Floor, New Academic Block", "09:00", "17:00", "HD Laser Projector, Surround Speakers, Podium Mic", "Maintain fixed tiered seating arrangement", None),

            # Common Rooms (2)
            ("Boys Common Room", "Common rooms", 60, "Ground Floor, Student Activity Centre", "09:00", "17:00", "Benches, Fans, Whiteboard", "Noise discipline required during exam weeks", None),
            ("Girls Common Room", "Common rooms", 60, "First Floor, Student Activity Centre", "09:00", "17:00", "Sofas, Tables, Mirrors, Notice Board", "Restricted entry for designated events", None),

            # Laboratories (3)
            ("Lab 11", "Laboratories", 40, "First Floor, Computer Centre", "09:00", "17:00", "40 All-in-One PCs, Gigabit LAN, Projector", "No food or beverages permitted inside", dept_map["Computer Science"].id),
            ("Lab 12", "Laboratories", 40, "First Floor, Computer Centre", "09:00", "17:00", "40 All-in-One PCs, High-speed Internet, Smart Board", "Shutdown all systems after completion", dept_map["Computer Science"].id),
            ("Lab 15", "Laboratories", 40, "Second Floor, Statistics Block", "09:00", "17:00", "40 Workstations with R/Python, Projector", "Statistical software installed", dept_map["Statistics"].id),

            # Sports Facilities (4)
            ("Sports Room", "Sports facilities", 30, "Grounds Pavilion", "08:00", "18:00", "Table Tennis boards, Chess boards, Carrom", "Return all sports kits to manager", None),
            ("Volleyball Court", "Sports facilities", 50, "Outdoor Sports Complex", "08:00", "18:00", "Official dimensions court with net", "Proper non-marking sports shoes mandatory", None),
            ("Short Ground", "Sports facilities", 200, "Adjacent to Canteen", "08:00", "18:00", "Turf cricket nets, Kabaddi arena", "Coordinate with ground staff before marking lines", None),
            ("Big Ground", "Sports facilities", 500, "Main College Campus Grounds", "08:00", "18:00", "Full football pitch, 400m running track, Stage area", "Permission required for heavy stage or vehicle setup", None),

            # Departmental Rooms (10)
            ("Commerce Department Room", "Departmental rooms", 40, "Room 101, Commerce Wing", "09:00", "17:00", "Conference Table, 30 Chairs, Smart TV", "Departmental priority applies", dept_map["Commerce"].id),
            ("Sanskrit Department Room", "Departmental rooms", 40, "Room 104, Arts Wing", "09:00", "17:00", "Meeting Table, Reference Library, Whiteboard", "Departmental priority applies", dept_map["Sanskrit"].id),
            ("Hindi Department Room", "Departmental rooms", 40, "Room 106, Arts Wing", "09:00", "17:00", "Discussion Tables, Projector Screen", "Departmental priority applies", dept_map["Hindi"].id),
            ("Mathematics Department Room", "Departmental rooms", 40, "Room 202, Science Block", "09:00", "17:00", "Chalkboards, Computing Station, Seminar Seating", "Departmental priority applies", dept_map["Mathematics"].id),
            ("Computer Science Department Room", "Departmental rooms", 40, "Room 205, Computer Centre", "09:00", "17:00", "Network Hub, Display TV, Conference Setup", "Departmental priority applies", dept_map["Computer Science"].id),
            ("Statistics Department Room", "Departmental rooms", 40, "Room 208, Statistics Wing", "09:00", "17:00", "Workstations, Projector, Meeting Table", "Departmental priority applies", dept_map["Statistics"].id),
            ("English Department Room", "Departmental rooms", 40, "Room 301, Humanities Wing", "09:00", "17:00", "Reading Corner, Discussion Circle, Projector", "Departmental priority applies", dept_map["English"].id),
            ("History Department Room", "Departmental rooms", 40, "Room 304, Humanities Wing", "09:00", "17:00", "Map Archives, Conference Table, Projector Screen", "Departmental priority applies", dept_map["History"].id),
            ("Political Science Department Room", "Departmental rooms", 40, "Room 307, Humanities Wing", "09:00", "17:00", "Debate Chamber Layout, Audio System", "Departmental priority applies", dept_map["Political Science"].id),
            ("Economics Department Room", "Departmental rooms", 40, "Room 310, Social Sciences Block", "09:00", "17:00", "Analytical Display, Conference Setup, Projector", "Departmental priority applies", dept_map["Economics"].id),
        ]

        count_res = 0
        for name, cat_name, cap, loc, s_time, e_time, eq, inst, dept_id in resources_seed:
            res = Resource.query.filter_by(name=name).first()
            if not res:
                res = Resource(
                    name=name,
                    category_id=cat_map[cat_name].id,
                    capacity=cap,
                    location=loc,
                    status='active',
                    booking_allowed=True,
                    approval_required=True,
                    operating_hours_start=s_time,
                    operating_hours_end=e_time,
                    equipment_available=eq,
                    special_instructions=inst,
                    department_id=dept_id
                )
                db.session.add(res)
                count_res += 1
        db.session.commit()
        print(f"Seeded {count_res} College Resources (Total registered in database: {Resource.query.count()}).")

        # 6. Equipment Inventory
        equipment_seed = [
            ("Projector", "Projectors", 5, "Excellent", "AV Control Room 102", "Active", True),
            ("Microphone", "Microphones and speakers", 10, "Good", "Sound Storage Room B", "Active", True),
            ("Speaker", "Microphones and speakers", 6, "Good", "Sound Storage Room B", "Active", True),
            ("Laptop", "Laptops", 20, "Excellent", "IT Support Center Lab 10", "Active", True),
            ("Chairs and tables", "Chairs and tables", 150, "Good", "Estate Maintenance Warehouse", "Active", True)
        ]
        for name, cat, qty, cond, loc, stat, avail in equipment_seed:
            eq = Equipment.query.filter_by(name=name).first()
            if not eq:
                eq = Equipment(
                    name=name,
                    category=cat,
                    total_quantity=qty,
                    condition=cond,
                    storage_location=loc,
                    maintenance_status=stat,
                    is_available=avail
                )
                db.session.add(eq)
        db.session.commit()
        print("Seeded equipment inventory.")

        # 7. Initial Users with Roles
        users_seed = [
            ("College Administrator", "admin@pgdav.du.ac.in", "admin123", "Administrator", None, "9876543210"),
            ("Dr. Rajesh Sharma", "faculty@pgdav.du.ac.in", "faculty123", "Faculty", dept_map["Commerce"].id, "9876543211"),
            ("Aarav Mehta (TechSoc)", "coord.tech@pgdav.du.ac.in", "coord123", "Society Coordinator", dept_map["Computer Science"].id, "9876543212"),
            ("Prof. Sunita Verma", "coord.cs@pgdav.du.ac.in", "deptcoord123", "Department Coordinator", dept_map["Computer Science"].id, "9876543213"),
            ("Rohan Gupta", "student@pgdav.du.ac.in", "student123", "Student", dept_map["Computer Science"].id, "9876543214"),
            ("Ananya Sen (Hyperion)", "coord.hyperion@pgdav.du.ac.in", "hyperion123", "Society Coordinator", dept_map["English"].id, "9876543215")
        ]
        user_map = {}
        for name, email, pwd, role, dept_id, phone in users_seed:
            u = User.query.filter_by(email=email).first()
            if not u:
                u = User(
                    name=name,
                    email=email,
                    role=role,
                    department_id=dept_id,
                    phone=phone,
                    is_active=True
                )
                u.set_password(pwd)
                db.session.add(u)
                db.session.flush()
            user_map[email] = u
        db.session.commit()
        print(f"Seeded {len(users_seed)} User accounts.")

        # Assign Society Memberships
        memberships_seed = [
            (user_map["coord.tech@pgdav.du.ac.in"].id, soc_map["TechSoc"].id, "Coordinator"),
            (user_map["coord.hyperion@pgdav.du.ac.in"].id, soc_map["Hyperion"].id, "President"),
            (user_map["student@pgdav.du.ac.in"].id, soc_map["TechSoc"].id, "Member"),
        ]
        for uid, sid, role in memberships_seed:
            m = SocietyMembership.query.filter_by(user_id=uid, society_id=sid).first()
            if not m:
                db.session.add(SocietyMembership(user_id=uid, society_id=sid, membership_role=role))
        db.session.commit()

        # 8. Add sample demo booking & maintenance for immediate visual inspection
        # Schedule maintenance on Lab 15 for next week
        target_date = date.today() + timedelta(days=5)
        m_start = datetime.combine(target_date, time(13, 0))
        m_end = datetime.combine(target_date, time(17, 0))
        lab15 = Resource.query.filter_by(name="Lab 15").first()
        if lab15 and not ResourceBlock.query.filter_by(resource_id=lab15.id).first():
            block = ResourceBlock(
                resource_id=lab15.id,
                start_at=m_start,
                end_at=m_end,
                reason="OS Upgrade and Network Cabling Maintenance",
                created_by_id=user_map["admin@pgdav.du.ac.in"].id
            )
            db.session.add(block)

        # Sample Approved Event: Annual Tech Symposium
        event_day = date.today() + timedelta(days=2)
        symposium = Event.query.filter_by(title="Annual Tech Symposium 2026").first()
        if not symposium:
            symposium = Event(
                title="Annual Tech Symposium 2026",
                description="Keynote talks, project exhibitions, and coding hackathon organised by TechSoc.",
                category="Technical",
                organiser_id=user_map["coord.tech@pgdav.du.ac.in"].id,
                department_id=dept_map["Computer Science"].id,
                society_id=soc_map["TechSoc"].id,
                expected_attendance=120,
                event_date=event_day,
                start_time=time(10, 0),
                end_time=time(16, 0),
                requirements="Projector, PA system, and 4 Laptops for demo stations"
            )
            db.session.add(symposium)
            db.session.flush()

            booking = BookingRequest(
                event_id=symposium.id,
                requester_id=user_map["coord.tech@pgdav.du.ac.in"].id,
                status=BookingRequest.STATUS_APPROVED
            )
            db.session.add(booking)
            db.session.flush()

            # Reserve New Seminar Hall (10:00 - 16:00)
            new_hall = Resource.query.filter_by(name="New Seminar Hall").first()
            if new_hall:
                db.session.add(BookingResource(
                    booking_id=booking.id,
                    resource_id=new_hall.id,
                    start_at=datetime.combine(event_day, time(10, 0)),
                    end_at=datetime.combine(event_day, time(16, 0)),
                    status='APPROVED'
                ))

            # Equipment allocated
            proj = Equipment.query.filter_by(name="Projector").first()
            mic = Equipment.query.filter_by(name="Microphone").first()
            lap = Equipment.query.filter_by(name="Laptop").first()
            if proj:
                db.session.add(EquipmentRequest(
                    booking_id=booking.id, equipment_id=proj.id, quantity=1,
                    start_at=datetime.combine(event_day, time(10, 0)), end_at=datetime.combine(event_day, time(16, 0))
                ))
            if mic:
                db.session.add(EquipmentRequest(
                    booking_id=booking.id, equipment_id=mic.id, quantity=2,
                    start_at=datetime.combine(event_day, time(10, 0)), end_at=datetime.combine(event_day, time(16, 0))
                ))
            if lap:
                db.session.add(EquipmentRequest(
                    booking_id=booking.id, equipment_id=lap.id, quantity=4,
                    start_at=datetime.combine(event_day, time(10, 0)), end_at=datetime.combine(event_day, time(16, 0))
                ))

            db.session.add(ApprovalHistory(
                booking_id=booking.id,
                admin_id=user_map["admin@pgdav.du.ac.in"].id,
                action='APPROVED',
                remarks="Event approved with New Seminar Hall and requested AV equipment."
            ))

        db.session.commit()
        print("Database seeding completed successfully!")

if __name__ == '__main__':
    try:
        seed_database()
    except Exception as e:
        print(f"\n[ERROR] Seeding encountered an error: {e}")
        import traceback
        traceback.print_exc()
