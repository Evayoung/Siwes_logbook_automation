"""Idempotent client-requested data corrections for deployed test records."""

from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy.orm import Session

from app.domain.models import Geofence, IndustrialPlacement, StudentProfile, SupervisorProfile, User, UserRole
from app.infrastructure.database.connection import get_db_session


SIWES_START = date(2026, 6, 10)
SIWES_END = SIWES_START + timedelta(days=174)
ANCHOR_LATITUDE = 6.602191
ANCHOR_LONGITUDE = 3.242510
ANCHOR_LOCATION = "Anchor University Lagos"
ANCHOR_SUPERVISOR = "Anchor University SIWES Desk (siwes@aul.edu.ng)"


SUPERVISOR_UPDATES = [
    ("ada.williams@university.edu.ng", "abiodin.mustapha@university.edu.ng", "Dr Abiodin Mustapha"),
    ("c.okeke@university.edu.ng", "u.umoren@university.edu.ng", "Mr U. M Umoren"),
    ("t.akinyemi@university.edu.ng", "owuna.fenibo@university.edu.ng", "Barr. Owuna Fenibo"),
]

STUDENT_UPDATES = [
    ("john.doe@student.university.edu.ng", "sopiribi.fenibo@student.university.edu.ng", "Sopiribi Owuna Fenibo"),
    ("ruth.ekanem@student.university.edu.ng", "godwin.chisom@student.university.edu.ng", "Godwin Praise Chisom"),
]


def _archive_duplicate(user: User, email: str) -> None:
    """Keep a duplicate row from blocking the canonical requested email."""
    user.email = f"archived-{user.id[:8]}-{email}"
    user.is_active = False


def _resolve_user(db: Session, old_email: str, new_email: str, role: UserRole) -> User | None:
    old_email = old_email.strip().lower()
    new_email = new_email.strip().lower()
    old_user = db.query(User).filter(User.email == old_email).first()
    new_user = db.query(User).filter(User.email == new_email).first()

    if old_user and new_user and old_user.id != new_user.id:
        # Preserve the established account because it may own logs/chats/calls.
        _archive_duplicate(new_user, new_email)
        db.flush()
        target = old_user
    else:
        target = new_user or old_user

    if target:
        target.email = new_email
        target.role = role
        target.is_active = True
    return target


def _ensure_supervisor_profile(db: Session, user: User) -> None:
    profile = db.query(SupervisorProfile).filter(SupervisorProfile.user_id == user.id).first()
    if profile:
        profile.faculty = profile.faculty or "Science"


def _ensure_anchor_placement(db: Session, profile: StudentProfile) -> IndustrialPlacement:
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
            supervisor_contact=ANCHOR_SUPERVISOR,
            geofence_id=geofence.id,
        )
        db.add(placement)
        db.flush()
        profile.placement_id = placement.id

    placement.company_name = ANCHOR_LOCATION
    placement.address = ANCHOR_LOCATION
    placement.supervisor_contact = ANCHOR_SUPERVISOR

    geofence = placement.geofence
    if not geofence:
        geofence = Geofence(
            latitude=ANCHOR_LATITUDE,
            longitude=ANCHOR_LONGITUDE,
            radius_meters=500,
        )
        db.add(geofence)
        db.flush()
        placement.geofence_id = geofence.id
    else:
        geofence.latitude = ANCHOR_LATITUDE
        geofence.longitude = ANCHOR_LONGITUDE
        geofence.radius_meters = 500

    return placement


def apply_usability_data_patch() -> None:
    """Apply the latest test-data corrections without resetting user activity."""
    db = get_db_session()
    try:
        supervisors: dict[str, User] = {}
        for old_email, new_email, full_name in SUPERVISOR_UPDATES:
            user = _resolve_user(db, old_email, new_email, UserRole.SUPERVISOR)
            if not user:
                continue
            user.full_name = full_name
            _ensure_supervisor_profile(db, user)
            supervisors[new_email] = user

        default_supervisor = supervisors.get("abiodin.mustapha@university.edu.ng")
        if not default_supervisor:
            default_supervisor = db.query(User).filter(User.email == "abiodin.mustapha@university.edu.ng").first()

        for old_email, new_email, full_name in STUDENT_UPDATES:
            user = _resolve_user(db, old_email, new_email, UserRole.STUDENT)
            if not user:
                continue
            user.full_name = full_name

            profile = db.query(StudentProfile).filter(StudentProfile.user_id == user.id).first()
            if not profile:
                continue

            profile.institution = "Anchor University"
            profile.siwes_start_date = SIWES_START
            profile.siwes_end_date = SIWES_END
            if default_supervisor:
                profile.assigned_supervisor_id = default_supervisor.id
            _ensure_anchor_placement(db, profile)

        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
