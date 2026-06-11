"""Apply client-requested usability test data updates in-place.

This is intentionally idempotent and does not reset logs, chats, calls, or
notifications. It updates existing users by old or new email, then updates the
linked profile, placement, and geofence records.
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


SIWES_START = date(2026, 6, 10)
SIWES_END = SIWES_START + timedelta(days=174)
ANCHOR_LATITUDE = 6.602191
ANCHOR_LONGITUDE = 3.242510
ANCHOR_LOCATION = "Anchor University Lagos"


SUPERVISOR_UPDATES = [
    {
        "old_email": "ada.williams@university.edu.ng",
        "new_email": "abiodin.mustapha@university.edu.ng",
        "full_name": "Dr Abiodin Mustapha",
    },
    {
        "old_email": "c.okeke@university.edu.ng",
        "new_email": "u.umoren@university.edu.ng",
        "full_name": "Mr U. M Umoren",
    },
    {
        "old_email": "t.akinyemi@university.edu.ng",
        "new_email": "owuna.fenibo@university.edu.ng",
        "full_name": "Barr. Owuna Fenibo",
    },
]


STUDENT_UPDATES = [
    {
        "old_email": "john.doe@student.university.edu.ng",
        "new_email": "sopiribi.fenibo@student.university.edu.ng",
        "full_name": "Sopiribi Owuna Fenibo",
    },
    {
        "old_email": "ruth.ekanem@student.university.edu.ng",
        "new_email": "godwin.chisom@student.university.edu.ng",
        "full_name": "Godwin Praise Chisom",
    },
]


def _find_user(db, old_email: str, new_email: str, role: UserRole) -> User | None:
    old_email = old_email.strip().lower()
    new_email = new_email.strip().lower()
    old_user = db.query(User).filter(User.email == old_email).first()
    new_user = db.query(User).filter(User.email == new_email).first()
    if old_user and new_user and old_user.id != new_user.id:
        raise RuntimeError(f"Both {old_email} and {new_email} exist for different users.")
    user = new_user or old_user
    if user:
        user.role = role
    return user


def _ensure_geofenced_placement(db, profile: StudentProfile) -> IndustrialPlacement:
    placement = None
    if profile.placement_id:
        placement = db.query(IndustrialPlacement).filter(IndustrialPlacement.id == profile.placement_id).first()

    if not placement:
        geofence = Geofence(
            latitude=ANCHOR_LATITUDE,
            longitude=ANCHOR_LONGITUDE,
            radius_meters=500,
        )
        db.add(geofence)
        db.flush()
        placement = IndustrialPlacement(
            company_name=ANCHOR_LOCATION,
            address=ANCHOR_LOCATION,
            supervisor_contact="Anchor University SIWES Desk (siwes@aul.edu.ng)",
            geofence_id=geofence.id,
        )
        db.add(placement)
        db.flush()
        profile.placement_id = placement.id

    placement.company_name = ANCHOR_LOCATION
    placement.address = ANCHOR_LOCATION
    placement.supervisor_contact = "Anchor University SIWES Desk (siwes@aul.edu.ng)"

    if placement.geofence:
        placement.geofence.latitude = ANCHOR_LATITUDE
        placement.geofence.longitude = ANCHOR_LONGITUDE
        placement.geofence.radius_meters = 500
    else:
        geofence = Geofence(
            latitude=ANCHOR_LATITUDE,
            longitude=ANCHOR_LONGITUDE,
            radius_meters=500,
        )
        db.add(geofence)
        db.flush()
        placement.geofence_id = geofence.id

    return placement


def apply_updates() -> None:
    db = get_db_session()
    try:
        supervisor_by_new_email: dict[str, User] = {}
        for item in SUPERVISOR_UPDATES:
            user = _find_user(db, item["old_email"], item["new_email"], UserRole.SUPERVISOR)
            if not user:
                print(f"WARNING: supervisor not found: {item['old_email']}")
                continue
            user.full_name = item["full_name"]
            user.email = item["new_email"]
            user.is_active = True
            profile = db.query(SupervisorProfile).filter(SupervisorProfile.user_id == user.id).first()
            if profile:
                profile.faculty = profile.faculty or "Science"
            supervisor_by_new_email[item["new_email"]] = user
            print(f"Updated supervisor: {user.full_name} <{user.email}>")

        default_supervisor = supervisor_by_new_email.get("abiodin.mustapha@university.edu.ng")
        for item in STUDENT_UPDATES:
            user = _find_user(db, item["old_email"], item["new_email"], UserRole.STUDENT)
            if not user:
                print(f"WARNING: student not found: {item['old_email']}")
                continue
            user.full_name = item["full_name"]
            user.email = item["new_email"]
            user.is_active = True

            profile = db.query(StudentProfile).filter(StudentProfile.user_id == user.id).first()
            if not profile:
                print(f"WARNING: student profile not found: {user.email}")
                continue

            profile.institution = "Anchor University"
            profile.siwes_start_date = SIWES_START
            profile.siwes_end_date = SIWES_END
            if default_supervisor:
                profile.assigned_supervisor_id = default_supervisor.id
            _ensure_geofenced_placement(db, profile)
            print(f"Updated student: {user.full_name} <{user.email}>")

        db.commit()
        print("Usability test data updates applied successfully.")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    apply_updates()
