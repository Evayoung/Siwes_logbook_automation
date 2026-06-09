"""Friendly manual data seeding wizard.

Run:
    python scripts/manual_seed.py

This script is intentionally prompt-based so a non-technical user can add
supervisors, students, and SIWES centers without editing JSON files.
"""

from __future__ import annotations

import sys
from datetime import date, timedelta
from pathlib import Path


current_dir = Path(__file__).resolve().parent
project_root = current_dir.parent
sys.path.append(str(project_root))

from app.domain.models.placement import Geofence, IndustrialPlacement
from app.domain.models.user import StudentProfile, SupervisorProfile, User, UserRole
from app.infrastructure.database.connection import get_db_session
from app.infrastructure.security.password import hash_password


def default_siwes_start() -> date:
    today = date.today()
    return today - timedelta(days=today.weekday())


def default_siwes_end(start: date) -> date:
    return start + timedelta(weeks=24, days=4)


def ask(label: str, default: str | None = None, required: bool = True) -> str:
    prompt = f"{label}"
    if default not in (None, ""):
        prompt += f" [{default}]"
    prompt += ": "

    while True:
        value = input(prompt).strip()
        if not value and default is not None:
            value = str(default)
        if value or not required:
            return value
        print("  This field is required. Please enter a value.")


def ask_bool(label: str, default: bool = True) -> bool:
    suffix = "Y/n" if default else "y/N"
    value = input(f"{label} ({suffix}): ").strip().lower()
    if not value:
        return default
    return value in {"y", "yes"}


def ask_date(label: str, default: date) -> date:
    while True:
        raw = ask(label, default.isoformat())
        try:
            return date.fromisoformat(raw)
        except ValueError:
            print("  Use YYYY-MM-DD format, for example 2026-06-08.")


def ask_float(label: str, default: float) -> float:
    while True:
        raw = ask(label, str(default))
        try:
            return float(raw)
        except ValueError:
            print("  Enter a number, for example 6.4549.")


def ask_int(label: str, default: int) -> int:
    while True:
        raw = ask(label, str(default))
        try:
            return int(raw)
        except ValueError:
            print("  Enter a whole number, for example 500.")


def staff_id_from_email(email: str) -> str:
    local = email.split("@", 1)[0].replace(".", "").replace("_", "")
    return f"STAFF/2026/{local[-4:].upper().rjust(4, 'X')}"


def upsert_supervisor(db, *, full_name: str, email: str, password: str, department: str) -> User:
    email = email.strip().lower()
    supervisor = db.query(User).filter(User.email == email).first()
    if supervisor:
        supervisor.full_name = full_name
        supervisor.role = UserRole.SUPERVISOR
        supervisor.is_active = True
        if password:
            supervisor.password_hash = hash_password(password)
        print(f"  Updated supervisor: {full_name}")
    else:
        supervisor = User(
            full_name=full_name,
            email=email,
            password_hash=hash_password(password or "password123"),
            role=UserRole.SUPERVISOR,
            is_active=True,
        )
        db.add(supervisor)
        db.flush()
        print(f"  Created supervisor: {full_name}")

    profile = db.query(SupervisorProfile).filter(SupervisorProfile.user_id == supervisor.id).first()
    if not profile:
        profile = SupervisorProfile(
            user_id=supervisor.id,
            staff_id=staff_id_from_email(email),
            faculty=department or "Science",
        )
        db.add(profile)
    else:
        profile.faculty = department or profile.faculty or "Science"
        profile.staff_id = profile.staff_id or staff_id_from_email(email)

    return supervisor


def upsert_student_with_center(db) -> None:
    print("\nStudent details")
    full_name = ask("Student full name")
    email = ask("Student email").lower()
    password = ask("Student password", "password123")
    matric_number = ask("Matric number")
    department = ask("Department", "Computer Science")

    print("\nAssigned university supervisor")
    supervisor_email = ask("Supervisor email").lower()
    supervisor = db.query(User).filter(User.email == supervisor_email).first()
    if not supervisor:
        print("  Supervisor was not found. Let us create the supervisor now.")
        supervisor = upsert_supervisor(
            db,
            full_name=ask("Supervisor full name"),
            email=supervisor_email,
            password=ask("Supervisor password", "password123"),
            department=ask("Supervisor department/faculty", department),
        )

    start_dt = ask_date("SIWES start date", default_siwes_start())
    end_dt = ask_date("SIWES end date", default_siwes_end(start_dt))

    print("\nSIWES center / placement details")
    company_name = ask("Company / SIWES center name")
    company_address = ask("Company address")
    company_supervisor_name = ask("Company supervisor name", required=False)
    company_supervisor_email = ask("Company supervisor email", required=False)
    latitude = ask_float("Center latitude", 6.4549)
    longitude = ask_float("Center longitude", 3.3947)
    radius = ask_int("Allowed GPS radius in meters", 500)

    student = db.query(User).filter(User.email == email).first()
    if student:
        student.full_name = full_name
        student.role = UserRole.STUDENT
        student.is_active = True
        if password:
            student.password_hash = hash_password(password)
        print(f"  Updated student: {full_name}")
    else:
        student = User(
            full_name=full_name,
            email=email,
            password_hash=hash_password(password or "password123"),
            role=UserRole.STUDENT,
            is_active=True,
        )
        db.add(student)
        db.flush()
        print(f"  Created student: {full_name}")

    profile = db.query(StudentProfile).filter(StudentProfile.user_id == student.id).first()
    if not profile:
        profile = StudentProfile(
            user_id=student.id,
            matriculation_number=matric_number,
            department=department,
            institution="University of Lagos",
            siwes_start_date=start_dt,
            siwes_end_date=end_dt,
        )
        db.add(profile)
        db.flush()
    else:
        profile.matriculation_number = matric_number
        profile.department = department
        profile.siwes_start_date = start_dt
        profile.siwes_end_date = end_dt

    profile.assigned_supervisor_id = supervisor.id

    placement = None
    if profile.placement_id:
        placement = db.query(IndustrialPlacement).filter(
            IndustrialPlacement.id == profile.placement_id
        ).first()

    supervisor_contact = f"{company_supervisor_name} ({company_supervisor_email})".strip()
    if not placement:
        geofence = Geofence(latitude=latitude, longitude=longitude, radius_meters=radius)
        db.add(geofence)
        db.flush()
        placement = IndustrialPlacement(
            company_name=company_name,
            address=company_address,
            supervisor_contact=supervisor_contact,
            geofence_id=geofence.id,
        )
        db.add(placement)
        db.flush()
        profile.placement_id = placement.id
    else:
        placement.company_name = company_name
        placement.address = company_address
        placement.supervisor_contact = supervisor_contact or placement.supervisor_contact
        if placement.geofence:
            placement.geofence.latitude = latitude
            placement.geofence.longitude = longitude
            placement.geofence.radius_meters = radius
        else:
            geofence = Geofence(latitude=latitude, longitude=longitude, radius_meters=radius)
            db.add(geofence)
            db.flush()
            placement.geofence_id = geofence.id

    print(f"  Linked {full_name} to {company_name}.")


def run() -> None:
    print("SIWES Manual Seed Wizard")
    print("========================")
    print("Press Enter to accept values shown in [brackets].\n")

    db = get_db_session()
    try:
        if ask_bool("Add or update supervisors first?", True):
            while True:
                print("\nSupervisor details")
                upsert_supervisor(
                    db,
                    full_name=ask("Supervisor full name"),
                    email=ask("Supervisor email"),
                    password=ask("Supervisor password", "password123"),
                    department=ask("Supervisor department/faculty", "Science"),
                )
                db.commit()
                if not ask_bool("Add another supervisor?", False):
                    break

        if ask_bool("\nAdd or update students and SIWES centers?", True):
            while True:
                upsert_student_with_center(db)
                db.commit()
                if not ask_bool("Add another student?", False):
                    break

        print("\nDone. Manual seed data saved successfully.")
    except KeyboardInterrupt:
        db.rollback()
        print("\nCancelled. No unfinished changes were saved.")
    except Exception as exc:
        db.rollback()
        print(f"\nError: {exc}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    run()
