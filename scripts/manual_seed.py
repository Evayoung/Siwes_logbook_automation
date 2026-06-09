"""Friendly manual/bulk data seeding wizard.

Run:
    python scripts/manual_seed.py
    python scripts/manual_seed.py --json data/manual_seed_template.json

The prompt mode is for one-by-one entry. The JSON mode is for bulk records.
"""

from __future__ import annotations

import sys
import argparse
import json
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


def upsert_supervisor(db, *, full_name: str, email: str, password: str = "password123", department: str = "Science") -> User:
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


def upsert_student_record(db, record: dict) -> None:
    full_name = str(record["full_name"]).strip()
    email = str(record["email"]).strip().lower()
    password = str(record.get("password") or "password123")
    matric_number = str(record.get("matric_number") or record.get("matric") or "")
    department = str(record.get("department") or "Computer Science")
    supervisor_email = str(record["supervisor_email"]).strip().lower()
    placement_data = record.get("placement") or {}

    supervisor = db.query(User).filter(User.email == supervisor_email).first()
    if not supervisor:
        supervisor_data = record.get("supervisor") or {}
        supervisor_name = supervisor_data.get("full_name") or f"Supervisor for {full_name}"
        print(f"  Supervisor not found for {full_name}. Creating {supervisor_name}.")
        supervisor = upsert_supervisor(
            db,
            full_name=supervisor_name,
            email=supervisor_email,
            password=supervisor_data.get("password") or "password123",
            department=supervisor_data.get("department") or department,
        )

    start_dt = parse_date_value(record.get("siwes_start_date") or placement_data.get("start_date"), default_siwes_start())
    end_dt = parse_date_value(record.get("siwes_end_date") or placement_data.get("end_date"), default_siwes_end(start_dt))

    company_name = str(placement_data.get("company_name") or record.get("company_name") or "Unknown SIWES Center")
    company_address = str(placement_data.get("company_address") or record.get("company_address") or "Address not provided")
    company_supervisor_name = str(placement_data.get("supervisor_name") or "")
    company_supervisor_email = str(placement_data.get("supervisor_email") or "")
    latitude = float(placement_data.get("latitude", record.get("latitude", 6.4549)))
    longitude = float(placement_data.get("longitude", record.get("longitude", 3.3947)))
    radius = int(placement_data.get("radius_meters", record.get("radius_meters", 500)))

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


def parse_date_value(value: str | date | None, fallback: date) -> date:
    if isinstance(value, date):
        return value
    if not value:
        return fallback
    try:
        return date.fromisoformat(str(value))
    except ValueError:
        return fallback


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
    supervisor_data = None
    if not supervisor:
        print("  Supervisor was not found. Let us create the supervisor now.")
        supervisor_data = {
            "full_name": ask("Supervisor full name"),
            "password": ask("Supervisor password", "password123"),
            "department": ask("Supervisor department/faculty", department),
        }

    start_dt = ask_date("SIWES start date", default_siwes_start())
    end_dt = ask_date("SIWES end date", default_siwes_end(start_dt))

    print("\nSIWES center / placement details")
    record = {
        "full_name": full_name,
        "email": email,
        "password": password,
        "matric_number": matric_number,
        "department": department,
        "supervisor_email": supervisor_email,
        "supervisor": supervisor_data,
        "siwes_start_date": start_dt.isoformat(),
        "siwes_end_date": end_dt.isoformat(),
        "placement": {
            "company_name": ask("Company / SIWES center name"),
            "company_address": ask("Company address"),
            "supervisor_name": ask("Company supervisor name", required=False),
            "supervisor_email": ask("Company supervisor email", required=False),
            "latitude": ask_float("Center latitude", 6.4549),
            "longitude": ask_float("Center longitude", 3.3947),
            "radius_meters": ask_int("Allowed GPS radius in meters", 500),
        },
    }
    upsert_student_record(db, record)


def load_json_records(path: Path) -> tuple[list[dict], list[dict]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, list):
        return [], data
    if not isinstance(data, dict):
        raise ValueError("JSON file must contain an object or a list of students.")
    supervisors = data.get("supervisors") or []
    students = data.get("students") or []
    if not isinstance(supervisors, list) or not isinstance(students, list):
        raise ValueError("'supervisors' and 'students' must be lists.")
    return supervisors, students


def run_json_import(path: Path) -> None:
    supervisors, students = load_json_records(path)
    db = get_db_session()
    try:
        print(f"Importing records from {path}")
        for supervisor in supervisors:
            upsert_supervisor(
                db,
                full_name=supervisor["full_name"],
                email=supervisor["email"],
                password=supervisor.get("password") or "password123",
                department=supervisor.get("department") or supervisor.get("faculty") or "Science",
            )
        for student in students:
            upsert_student_record(db, student)
        db.commit()
        print(f"Done. Imported {len(supervisors)} supervisor(s) and {len(students)} student(s).")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def run_interactive() -> None:
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
    parser = argparse.ArgumentParser(description="Add SIWES supervisors, students, and centers.")
    parser.add_argument(
        "--json",
        type=Path,
        help="Bulk import from a JSON file instead of using prompts.",
    )
    args = parser.parse_args()
    if args.json:
        run_json_import(args.json)
    else:
        run_interactive()
