"""User authentication and profile models.

Defines the core user entity and role-based profile extensions for
students and supervisors in the SIWES system.
"""

import enum
import uuid
from datetime import datetime, date
from typing import Optional

from sqlalchemy import Column, String, Boolean, Enum, DateTime, ForeignKey, Date, Text
from sqlalchemy.orm import relationship, backref

from .base import Base, TimestampMixin


class UserRole(enum.Enum):
    """Enumeration of user roles in the system.
    
    Defines the two primary user types with distinct permissions and
    access levels in the SIWES logbook system.
    
    Attributes:
        STUDENT: Student/trainee role with permissions to create logs
                and communicate with assigned supervisor.
        SUPERVISOR: University supervisor role with permissions to review
                   logs and monitor assigned students.
    """
    STUDENT = "student"
    SUPERVISOR = "supervisor"


class User(Base, TimestampMixin):
    """Core user authentication entity.
    
    Represents an authenticated user in the system. Each user has exactly
    one role (STUDENT or SUPERVISOR) and is extended by either StudentProfile
    or SupervisorProfile accordingly.
    
    Attributes:
        id: Unique identifier (UUID string format).
        email: User's email address, unique across system, used for login.
        password_hash: Bcrypt hashed password (never store plaintext).
        role: User's role determining permissions and UI access.
        is_active: Whether account is active and can authenticate.
        last_login_at: Timestamp of most recent successful login (UTC).
        student_profile: Related StudentProfile if role is STUDENT (1-to-1).
        supervisor_profile: Related SupervisorProfile if role is SUPERVISOR (1-to-1).
    
    Example:
        >>> from app.infrastructure.security.password import hash_password
        >>> user = User(
        ...     id=str(uuid.uuid4()),
        ...     email="student@university.edu",
        ...     password_hash=hash_password("secure_password"),
        ...     role=UserRole.STUDENT,
        ...     is_active=True
        ... )
        >>> print(f"Created user: {user.email}")
        Created user: student@university.edu
    
    Note:
        - Email must be unique and is case-insensitive
        - Password must be hashed using bcrypt before storage
        - Inactive users cannot log in but data is preserved
    """
    
    __tablename__ = "users"
    
    id = Column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        comment="Unique user identifier (UUID format)"
    )
    email = Column(
        String(255),
        unique=True,
        nullable=False,
        index=True,
        comment="User email address (login credential, case-insensitive)"
    )
    password_hash = Column(
        String(255),
        nullable=False,
        comment="Bcrypt hashed password (never store plaintext)"
    )
    full_name = Column(
        String(100),
        nullable=False,
        comment="User's full legal name"
    )
    role = Column(
        Enum(UserRole),
        nullable=False,
        comment="User role determining permissions (student or supervisor)"
    )
    is_active = Column(
        Boolean,
        default=True,
        nullable=False,
        comment="Account active status - False prevents login"
    )
    last_login_at = Column(
        DateTime,
        nullable=True,
        comment="UTC timestamp of last successful login"
    )





class StudentProfile(Base, TimestampMixin):
    """Extended profile for student users.
    
    Contains SIWES-specific information for students including academic
    details, training period, and industrial placement assignment.
    
    Attributes:
        user_id: Foreign key to User table (primary key, 1-to-1).
        matriculation_number: Student's unique matriculation/registration number.
        department: Academic department (e.g., "Computer Science").
        institution: Name of educational institution.
        siwes_start_date: Start date of 25-week SIWES training period.
        siwes_end_date: End date of SIWES training period.
        placement_id: Foreign key to assigned IndustrialPlacement (nullable).
        user: Related User entity (back-reference).
        placement: Related IndustrialPlacement entity.
        daily_logs: Collection of student's daily log entries.
    
    Example:
        >>> profile = StudentProfile(
        ...     user_id=user.id,
        ...     matriculation_number="CSC/2020/001",
        ...     department="Computer Science",
        ...     institution="University of Lagos",
        ...     siwes_start_date=date(2026, 1, 6),
        ...     siwes_end_date=date(2026, 6, 27)
        ... )
        >>> print(f"SIWES duration: {(profile.siwes_end_date - profile.siwes_start_date).days} days")
        SIWES duration: 172 days
    
    Note:
        - SIWES period is typically 25 weeks (~175 days)
        - placement_id is nullable until student is assigned
        - Matriculation number must be unique across institution
    """
    
    __tablename__ = "student_profiles"
    
    user_id = Column(
        String(36),
        ForeignKey(User.id, ondelete='CASCADE'),
        primary_key=True,
        comment="Foreign key to users table (1-to-1 relationship)"
    )
    matriculation_number = Column(
        String(50),
        unique=True,
        nullable=False,
        index=True,
        comment="Student matriculation/registration number (unique)"
    )
    department = Column(
        String(100),
        nullable=False,
        comment="Academic department name"
    )
    institution = Column(
        String(200),
        nullable=False,
        comment="Educational institution name"
    )
    siwes_start_date = Column(
        Date,
        nullable=False,
        comment="SIWES training period start date"
    )
    siwes_end_date = Column(
        Date,
        nullable=False,
        comment="SIWES training period end date (typically start + 25 weeks)"
    )
    placement_id = Column(
        String(36),
        ForeignKey('industrial_placements.id'),
        nullable=True,
        comment="Foreign key to industrial placement (nullable until assigned)"
    )
    assigned_supervisor_id = Column(
        String(36),
        ForeignKey('users.id'),
        nullable=True,
        comment="Foreign key to university supervisor"
    )
    setting_location_service = Column(
        Boolean,
        default=True,
        nullable=False,
        comment="Whether student enables location service prompts in app UI",
    )
    setting_offline_mode = Column(
        Boolean,
        default=False,
        nullable=False,
        comment="Whether student enables offline-first behavior in app UI",
    )
    setting_notifications = Column(
        Boolean,
        default=True,
        nullable=False,
        comment="Whether student wants in-app notification prompts",
    )
    
    # Relationships
    user = relationship("User", foreign_keys=[user_id], viewonly=True)
    supervisor = relationship("User", foreign_keys=[assigned_supervisor_id])
    placement = relationship("IndustrialPlacement", back_populates="students")


class SupervisorProfile(Base, TimestampMixin):
    """Extended profile for supervisor users.
    
    Contains university supervisor information including staff identification
    and faculty affiliation. Supervisors review student logs and provide guidance.
    
    Attributes:
        user_id: Foreign key to User table (primary key, 1-to-1).
        staff_id: University staff identification number (unique).
        faculty: Faculty or department affiliation.
        user: Related User entity (back-reference).
        reviewed_logs: Collection of logs reviewed by this supervisor.
    
    Example:
        >>> profile = SupervisorProfile(
        ...     user_id=user.id,
        ...     staff_id="STAFF/2020/042",
        ...     faculty="Faculty of Science"
        ... )
        >>> print(f"Supervisor: {profile.staff_id} - {profile.faculty}")
        Supervisor: STAFF/2020/042 - Faculty of Science
    
    Note:
        - Staff ID must be unique across institution
        - Supervisors can review logs from multiple students
        - Faculty field helps with administrative organization
    """
    
    __tablename__ = "supervisor_profiles"
    
    user_id = Column(
        String(36),
        ForeignKey(User.id, ondelete='CASCADE'),
        primary_key=True,
        comment="Foreign key to users table (1-to-1 relationship)"
    )
    staff_id = Column(
        String(50),
        unique=True,
        nullable=False,
        index=True,
        comment="University staff identification number (unique)"
    )
    faculty = Column(
        String(100),
        nullable=False,
        comment="Faculty or department affiliation"
    )
    
    # Relationships
    user = relationship("User", foreign_keys=[user_id], viewonly=True)
