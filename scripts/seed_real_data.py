"""Seed realistic supervisor/student/placement data.

Reads from:
- data/supervisors.json
- data/students.json

Behavior:
- Idempotent updates for existing users/profiles.
- Ensures SIWES dates are current (from input data, defaulting to 2026 window).
- Creates or updates placement + geofence for each student.
"""

import json
import sys
from datetime import date
from pathlib import Path

# Add project root to path
current_dir = Path(__file__).resolve().parent
project_root = current_dir.parent
sys.path.append(str(project_root))

from app.infrastructure.database.connection import get_db_session
from app.domain.models.user import User, UserRole, StudentProfile, SupervisorProfile
from app.domain.models.placement import IndustrialPlacement, Geofence
from app.infrastructure.security.password import hash_password as get_password_hash

DEFAULT_SIWES_START = date(2026, 6, 8)
DEFAULT_SIWES_END = date(2026, 11, 27)
DEFAULT_INSTITUTION = "University of Lagos"


def parse_date(value: str | None, fallback: date) -> date:
    if not value:
        return fallback
    try:
        return date.fromisoformat(value)
    except Exception:
        return fallback


def normalized_staff_id(email: str) -> str:
    local = (email or "staff").split("@")[0].replace(".", "").replace("_", "")
    suffix = local[-4:].upper().rjust(4, "X")
    return f"STAFF/2026/{suffix}"


def seed_data():
    db = get_db_session()
    try:
        print("Seeding realistic data...")

        supervisors_path = project_root / "data" / "supervisors.json"
        students_path = project_root / "data" / "students.json"

        with open(supervisors_path, "r", encoding="utf-8") as f:
            supervisors_data = json.load(f)

        with open(students_path, "r", encoding="utf-8") as f:
            students_data = json.load(f)

        supervisor_map: dict[str, User] = {}
        print(f"Ensuring {len(supervisors_data)} supervisors...")

        for sup_data in supervisors_data:
            email = sup_data["email"].strip().lower()
            full_name = sup_data["full_name"].strip()
            is_active = bool(sup_data.get("is_active", True))

            supervisor = db.query(User).filter(User.email == email).first()
            if not supervisor:
                supervisor = User(
                    full_name=full_name,
                    email=email,
                    password_hash=get_password_hash(sup_data.get("password") or "password123"),
                    role=UserRole.SUPERVISOR,
                    is_active=is_active,
                )
                db.add(supervisor)
                db.flush()
                print(f"  Created supervisor: {full_name}")
            else:
                supervisor.full_name = full_name
                supervisor.role = UserRole.SUPERVISOR
                supervisor.is_active = is_active
                if sup_data.get("password"):
                    supervisor.password_hash = get_password_hash(sup_data["password"])
                print(f"  Updated supervisor: {full_name}")

            profile = db.query(SupervisorProfile).filter(SupervisorProfile.user_id == supervisor.id).first()
            if not profile:
                profile = SupervisorProfile(
                    user_id=supervisor.id,
                    staff_id=normalized_staff_id(email),
                    faculty="Science",
                )
                db.add(profile)
            else:
                if not profile.staff_id:
                    profile.staff_id = normalized_staff_id(email)
                if not profile.faculty:
                    profile.faculty = "Science"

            supervisor_map[email] = supervisor

        db.commit()

        print(f"Ensuring {len(students_data)} students, profiles, placements...")

        for stud_data in students_data:
            email = stud_data["email"].strip().lower()
            full_name = stud_data["full_name"].strip()
            is_active = bool(stud_data.get("is_active", True))

            student = db.query(User).filter(User.email == email).first()
            if not student:
                student = User(
                    full_name=full_name,
                    email=email,
                    password_hash=get_password_hash(stud_data.get("password") or "password123"),
                    role=UserRole.STUDENT,
                    is_active=is_active,
                )
                db.add(student)
                db.flush()
                print(f"  Created student: {full_name}")
            else:
                student.full_name = full_name
                student.role = UserRole.STUDENT
                student.is_active = is_active
                if stud_data.get("password"):
                    student.password_hash = get_password_hash(stud_data["password"])
                print(f"  Updated student: {full_name}")

            placement_data = stud_data.get("placement") or {}
            start_dt = parse_date(placement_data.get("start_date"), DEFAULT_SIWES_START)
            end_dt = parse_date(placement_data.get("end_date"), DEFAULT_SIWES_END)

            profile = db.query(StudentProfile).filter(StudentProfile.user_id == student.id).first()
            if not profile:
                profile = StudentProfile(
                    user_id=student.id,
                    matriculation_number=stud_data.get("matric_number", ""),
                    department=stud_data.get("department", "Computer Science"),
                    institution=DEFAULT_INSTITUTION,
                    siwes_start_date=start_dt,
                    siwes_end_date=end_dt,
                )
                db.add(profile)
                db.flush()
            else:
                profile.matriculation_number = stud_data.get("matric_number", profile.matriculation_number)
                profile.department = stud_data.get("department", profile.department)
                profile.institution = profile.institution or DEFAULT_INSTITUTION
                profile.siwes_start_date = start_dt
                profile.siwes_end_date = end_dt

            supervisor_email = (stud_data.get("supervisor_email") or "").strip().lower()
            supervisor = supervisor_map.get(supervisor_email)
            if supervisor:
                profile.assigned_supervisor_id = supervisor.id
            else:
                print(f"    WARNING: Supervisor not found for {email}: {supervisor_email}")

            if placement_data:
                lat = float(placement_data.get("latitude", 6.5244))
                lng = float(placement_data.get("longitude", 3.3792))
                radius = int(placement_data.get("radius_meters", 500))

                placement = None
                if profile.placement_id:
                    placement = db.query(IndustrialPlacement).filter(IndustrialPlacement.id == profile.placement_id).first()

                if not placement:
                    geofence = Geofence(latitude=lat, longitude=lng, radius_meters=radius)
                    db.add(geofence)
                    db.flush()

                    supervisor_contact = (
                        f"{placement_data.get('supervisor_name', '')} "
                        f"({placement_data.get('supervisor_email', '')})"
                    ).strip()

                    placement = IndustrialPlacement(
                        company_name=placement_data.get("company_name", "Unknown Company"),
                        address=placement_data.get("company_address", "Unknown Address"),
                        supervisor_contact=supervisor_contact,
                        geofence_id=geofence.id,
                    )
                    db.add(placement)
                    db.flush()
                    profile.placement_id = placement.id
                    print(f"    Created placement: {placement.company_name}")
                else:
                    placement.company_name = placement_data.get("company_name", placement.company_name)
                    placement.address = placement_data.get("company_address", placement.address)
                    placement.supervisor_contact = (
                        f"{placement_data.get('supervisor_name', '')} "
                        f"({placement_data.get('supervisor_email', '')})"
                    ).strip() or placement.supervisor_contact

                    if placement.geofence:
                        placement.geofence.latitude = lat
                        placement.geofence.longitude = lng
                        placement.geofence.radius_meters = radius
                    else:
                        geofence = Geofence(latitude=lat, longitude=lng, radius_meters=radius)
                        db.add(geofence)
                        db.flush()
                        placement.geofence_id = geofence.id

            db.flush()

        db.commit()
        print("Data seeding completed successfully.")

    except Exception as e:
        print(f"Error seeding data: {e}")
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed_data()
