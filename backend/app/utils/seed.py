"""
ERP Seed Data Generator — creates realistic test data for workflow testing.

Usage:
    cd backend
    DATABASE_URL="..." SECRET_KEY="..." python -m app.utils.seed

Creates:
- 1 Society (AR Residency)
- 3 Wings (A, B, C)
- 15 Flats (5 per wing)
- Test users: admin, committee, security, staff, 5 residents
- 3 Staff members with shifts and duties
- Sample attendance for current week
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from datetime import date, timedelta, datetime
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.core.security import hash_password
from app.models.user import User, UserRole, UserStatus
from app.models.role import Role
from app.models.society import Society
from app.models.wing import Wing
from app.models.flat import Flat, FlatType, OccupancyStatus
from app.models.resident import Resident, ResidentType
from app.models.vehicle import Vehicle, VehicleType
from app.modules.staff.models.staff import (
    Staff, StaffShift, DutyAssignment, StaffAttendance,
    StaffDepartment, StaffStatus, ShiftType, AttendanceStatus,
)

ROLES    = ["Admin", "Committee", "Resident", "Security", "Staff"]
TODAY    = date.today()
PASSWORD = "Test@12345"


def get_or_create_role(db: Session, name: str) -> Role:
    r = db.query(Role).filter(Role.name == name).first()
    if not r:
        r = Role(name=name, description=f"{name} role")
        db.add(r); db.flush()
    return r


def create_user(db: Session, email: str, full_name: str, role_name: str,
                phone: str = None) -> User:
    existing = db.query(User).filter(User.email == email).first()
    if existing:
        print(f"  [skip] User {email} already exists")
        return existing
    role = get_or_create_role(db, role_name)
    user = User(
        email=email, full_name=full_name, phone=phone,
        hashed_password=hash_password(PASSWORD),
        status=UserStatus.ACTIVE,
    )
    db.add(user); db.flush()
    db.add(UserRole(user_id=user.id, role_id=role.id))
    print(f"  [✓] User: {email}  role={role_name}")
    return user


def run_seed():
    db = SessionLocal()
    try:
        print("\n🌱 AR Society ERP — Seed Data Generator")
        print("=" * 50)

        # ── Roles ─────────────────────────────────────────────────────────────
        print("\n[1] Creating roles...")
        roles = {name: get_or_create_role(db, name) for name in ROLES}
        db.flush()

        # ── Test Users ────────────────────────────────────────────────────────
        print("\n[2] Creating test users...")
        admin     = create_user(db, "admin@arsociety.com",     "Admin User",     "Admin",     "9000000001")
        committee = create_user(db, "committee@arsociety.com", "Committee User", "Committee", "9000000002")
        security  = create_user(db, "security@arsociety.com",  "Security Guard", "Security",  "9000000003")
        staff1    = create_user(db, "staff1@arsociety.com",    "Staff One",      "Staff",     "9000000004")

        residents_data = [
            ("res1@arsociety.com", "Rahul Sharma",   "9001001001"),
            ("res2@arsociety.com", "Priya Patel",    "9001001002"),
            ("res3@arsociety.com", "Amit Kumar",     "9001001003"),
            ("res4@arsociety.com", "Sunita Joshi",   "9001001004"),
            ("res5@arsociety.com", "Deepak Verma",   "9001001005"),
        ]
        res_users = [create_user(db, e, n, "Resident", p) for e, n, p in residents_data]

        # ── Society ───────────────────────────────────────────────────────────
        print("\n[3] Creating society...")
        society = db.query(Society).filter(Society.name == "AR Residency").first()
        if not society:
            society = Society(
                name="AR Residency", society_code="ARS001",
                address="Plot 12, Sector 7, MIDC", city="Mumbai",
                state="Maharashtra", pincode="400001", country="India",
                timezone="Asia/Kolkata",
                contact_email="management@arsociety.com",
                contact_phone="9000000000",
                emergency_contact_name="Admin User",
                emergency_contact_phone="9000000001",
                total_wings=3, total_flats=15,
                require_visitor_approval=True,
                allow_tenant_portal=True,
            )
            db.add(society); db.flush()
            print(f"  [✓] Society: {society.name}")
        else:
            print(f"  [skip] Society already exists")

        # ── Wings ─────────────────────────────────────────────────────────────
        print("\n[4] Creating wings...")
        wings = []
        for code, name in [("A","Wing A"),("B","Wing B"),("C","Wing C")]:
            w = db.query(Wing).filter(Wing.society_id==society.id, Wing.name==name).first()
            if not w:
                w = Wing(society_id=society.id, name=name, code=code, total_floors=5)
                db.add(w); db.flush()
                print(f"  [✓] {name}")
            wings.append(w)

        # ── Flats ─────────────────────────────────────────────────────────────
        print("\n[5] Creating flats...")
        all_flats = []
        for wing in wings:
            for floor in range(1, 6):
                flat_num = f"{floor}0{1}" if floor < 10 else f"{floor}01"
                fn = f"{wing.code}{floor}01"
                f = db.query(Flat).filter(Flat.wing_id==wing.id, Flat.flat_number==fn).first()
                if not f:
                    f = Flat(
                        wing_id=wing.id, flat_number=fn,
                        floor=floor, flat_type=FlatType.TWO_BHK,
                        area_sqft=850.0,
                        occupancy_status=OccupancyStatus.OWNER_OCCUPIED if floor <= 3 else OccupancyStatus.VACANT,
                    )
                    db.add(f); db.flush()
                all_flats.append(f)
        print(f"  [✓] {len(all_flats)} flats created")

        # ── Residents ─────────────────────────────────────────────────────────
        print("\n[6] Creating residents...")
        for i, (user, flat) in enumerate(zip(res_users, all_flats[:5])):
            res = db.query(Resident).filter(Resident.flat_id==flat.id).first()
            if not res:
                res = Resident(
                    flat_id=flat.id, user_id=user.id,
                    full_name=user.full_name, phone=user.phone,
                    email=user.email, resident_type=ResidentType.OWNER,
                    is_primary=True, move_in_date=TODAY - timedelta(days=365),
                    kyc_verified=True,
                )
                db.add(res); db.flush()
                print(f"  [✓] Resident: {user.full_name} → {flat.flat_number}")

        # ── Vehicles ──────────────────────────────────────────────────────────
        print("\n[7] Creating vehicles...")
        vehicles_data = [
            ("MH01AA0001", VehicleType.CAR,        "Honda",  "City",   "White"),
            ("MH01AA0002", VehicleType.MOTORCYCLE,  "Hero",   "Splendor","Black"),
            ("MH01AA0003", VehicleType.CAR,         "Maruti", "Swift",  "Red"),
        ]
        for vnum, vtype, make, model, color in vehicles_data:
            v = db.query(Vehicle).filter(Vehicle.vehicle_number==vnum).first()
            if not v:
                v = Vehicle(
                    society_id=society.id, flat_id=all_flats[0].id,
                    vehicle_number=vnum, vehicle_type=vtype,
                    make=make, model=model, color=color,
                    registered_by=admin.id,
                )
                db.add(v); db.flush()
                print(f"  [✓] Vehicle: {vnum}")

        # ── Shifts ────────────────────────────────────────────────────────────
        print("\n[8] Creating staff shifts...")
        from datetime import time
        morning_shift = db.query(StaffShift).filter(
            StaffShift.society_id==society.id, StaffShift.name=="Morning Shift"
        ).first()
        if not morning_shift:
            morning_shift = StaffShift(
                society_id=society.id, name="Morning Shift",
                shift_type=ShiftType.MORNING,
                start_time=time(6,0), end_time=time(14,0),
            )
            db.add(morning_shift); db.flush()
            print("  [✓] Morning Shift (06:00-14:00)")

        # ── Staff Members ─────────────────────────────────────────────────────
        print("\n[9] Creating staff members...")
        staff_members_data = [
            (security, "EMP-0001", StaffDepartment.SECURITY,   "Security Guard"),
            (staff1,   "EMP-0002", StaffDepartment.HOUSEKEEPING,"Housekeeping"),
        ]
        staff_objs = []
        for user, code, dept, designation in staff_members_data:
            s = db.query(Staff).filter(Staff.employee_code==code).first()
            if not s:
                s = Staff(
                    society_id=society.id, user_id=user.id,
                    employee_code=code, full_name=user.full_name,
                    mobile=user.phone or "9000000000",
                    department=dept, shift_id=morning_shift.id,
                    status=StaffStatus.ACTIVE,
                    joining_date=TODAY - timedelta(days=180),
                )
                db.add(s); db.flush()
                print(f"  [✓] Staff: {s.full_name} ({code})")
            staff_objs.append(s)

        # ── Attendance (last 5 days) ───────────────────────────────────────────
        print("\n[10] Seeding attendance data...")
        for staff_obj in staff_objs:
            for days_ago in range(5, 0, -1):
                att_date = TODAY - timedelta(days=days_ago)
                existing_att = db.query(StaffAttendance).filter(
                    StaffAttendance.staff_id==staff_obj.id,
                    StaffAttendance.attendance_date==att_date,
                ).first()
                if not existing_att:
                    att = StaffAttendance(
                        society_id=society.id, staff_id=staff_obj.id,
                        attendance_date=att_date,
                        status=AttendanceStatus.PRESENT,
                        check_in_time=datetime.combine(att_date, datetime.min.time()).replace(hour=6, minute=5),
                        check_out_time=datetime.combine(att_date, datetime.min.time()).replace(hour=14, minute=10),
                        working_hours=8.08,
                    )
                    db.add(att)
        print(f"  [✓] Attendance seeded for last 5 days")

        db.commit()

        print("\n✅ Seed data created successfully!")
        print("\n📋 Test Credentials (password: Test@12345)")
        print("-" * 45)
        for email, role in [
            ("admin@arsociety.com",     "Admin"),
            ("committee@arsociety.com", "Committee"),
            ("security@arsociety.com",  "Security"),
            ("staff1@arsociety.com",    "Staff"),
            ("res1@arsociety.com",      "Resident"),
        ]:
            print(f"  {role:12s}  {email}")
        print(f"\n🌐 Swagger: https://arsocietyapp-production.up.railway.app/docs")

    except Exception as e:
        db.rollback()
        print(f"\n❌ Seed failed: {e}")
        import traceback; traceback.print_exc()
    finally:
        db.close()


if __name__ == "__main__":
    run_seed()
