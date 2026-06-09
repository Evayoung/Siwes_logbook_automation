"""Daily log entry models.

Defines the core DailyLog entity for student activity tracking,
including offline sync support and geofence validation results.
This is the most critical model in the system as it handles the
25-week logging process with offline-first architecture.
"""

import enum
import uuid
from datetime import datetime, date
from typing import Optional

from sqlalchemy import Column, String, Date, Text, Float, DateTime, ForeignKey, Enum, Index, Integer
from sqlalchemy.orm import relationship

from .base import Base, TimestampMixin


class LogStatus(enum.Enum):
    """Lifecycle status of a daily log entry.
    
    Defines the progression of a log from creation to final review.
    Once a log reaches VERIFIED or FLAGGED, it becomes immutable.
    
    Attributes:
        DRAFT: Log created locally but not finalized by student.
        PENDING_REVIEW: Submitted and awaiting supervisor review.
        VERIFIED: Approved by supervisor, counts toward completion.
        FLAGGED: Rejected or marked for attention by supervisor.
    """
    DRAFT = "draft"
    PENDING_REVIEW = "pending_review"
    VERIFIED = "verified"
    FLAGGED = "flagged"


class LocationStatus(enum.Enum):
    """Geofence validation result for a log entry.
    
    Indicates whether the student was within the approved geofence
    boundary when creating the log entry.
    
    Attributes:
        WITHIN: Location is within approved geofence boundary.
        OUTSIDE: Location is outside geofence boundary (flagged).
        UNKNOWN: Location data unavailable or permission denied.
    """
    WITHIN = "within"
    OUTSIDE = "outside"
    UNKNOWN = "unknown"


class DailyLog(Base, TimestampMixin):
    """Daily activity log entry entity.
    
    Represents a single day's SIWES activity record. This is the core
    entity of the system, supporting offline creation with eventual
    synchronization via client_uuid for idempotency.
    
    The 25-week SIWES period consists of approximately 125 working days
    (5 days/week × 25 weeks). Each day requires one log entry.
    
    Attributes:
        id: Server-generated unique identifier (UUID).
        client_uuid: Client-generated UUID for offline sync idempotency.
        student_id: Foreign key to User (student who created log).
        placement_id: Foreign key to IndustrialPlacement.
        log_date: Date of the logged activity (must be within SIWES period).
        week_number: Week number (1-25) within SIWES period.
        activity_description: Detailed description of daily activities.
        latitude: GPS latitude where log was created (nullable).
        longitude: GPS longitude where log was created (nullable).
        distance_from_geofence: Calculated distance from geofence center (meters).
        location_status: Result of geofence validation.
        status: Current lifecycle status of the log.
        created_offline_at: Timestamp when created offline (nullable).
        synced_at: Timestamp when synced to server (nullable).
        reviewed_at: Timestamp when reviewed by supervisor (nullable).
        reviewer_id: Foreign key to User (supervisor who reviewed).
        reviewer_comment: Supervisor's review comments (nullable).
        student: Related StudentProfile entity.
        placement: Related IndustrialPlacement entity.
        reviewer: Related SupervisorProfile entity.
    
    Example:
        >>> log = DailyLog(
        ...     id=str(uuid.uuid4()),
        ...     client_uuid=str(uuid.uuid4()),
        ...     student_id=student.id,
        ...     placement_id=placement.id,
        ...     log_date=date(2026, 1, 24),
        ...     week_number=3,
        ...     activity_description="Learned database design and normalization",
        ...     latitude=6.5244,
        ...     longitude=3.3792
        ... )
        >>> print(f"Week {log.week_number}, Day: {log.log_date}")
        Week 3, Day: 2026-01-24
    
    Note:
        - client_uuid ensures idempotent sync (prevents duplicates)
        - Logs become immutable after status reaches VERIFIED or FLAGGED
        - Location data may be null if permission denied or unavailable
        - week_number is calculated from log_date and SIWES start date
        - One log per date per student (enforced at service layer)
    """
    
    __tablename__ = "daily_logs"
    
    id = Column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        comment="Server-generated unique identifier (UUID)"
    )
    client_uuid = Column(
        String(36),
        unique=True,
        nullable=False,
        index=True,
        comment="Client-generated UUID for sync idempotency"
    )
    student_id = Column(
        String(36),
        ForeignKey('users.id'),
        nullable=False,
        index=True,
        comment="Foreign key to student user"
    )
    placement_id = Column(
        String(36),
        ForeignKey('industrial_placements.id'),
        nullable=False,
        comment="Foreign key to industrial placement"
    )
    log_date = Column(
        Date,
        nullable=False,
        index=True,
        comment="Date of logged activity (must be within SIWES period)"
    )
    week_number = Column(
        Integer,
        nullable=False,
        comment="Week number (1-25) within SIWES period"
    )
    activity_description = Column(
        Text,
        nullable=False,
        comment="Detailed description of daily activities"
    )
    latitude = Column(
        Float,
        nullable=True,
        comment="GPS latitude where log was created"
    )
    longitude = Column(
        Float,
        nullable=True,
        comment="GPS longitude where log was created"
    )
    distance_from_geofence = Column(
        Float,
        nullable=True,
        comment="Calculated distance from geofence center (meters)"
    )
    location_status = Column(
        Enum(LocationStatus),
        default=LocationStatus.UNKNOWN,
        nullable=False,
        comment="Geofence validation result"
    )
    status = Column(
        Enum(LogStatus),
        default=LogStatus.PENDING_REVIEW,
        nullable=False,
        index=True,
        comment="Current lifecycle status"
    )
    created_offline_at = Column(
        DateTime,
        nullable=True,
        comment="UTC timestamp when created offline"
    )
    synced_at = Column(
        DateTime,
        nullable=True,
        comment="UTC timestamp when synced to server"
    )
    reviewed_at = Column(
        DateTime,
        nullable=True,
        comment="UTC timestamp when reviewed by supervisor"
    )
    reviewer_id = Column(
        String(36),
        ForeignKey('users.id'),
        nullable=True,
        comment="Foreign key to supervisor who reviewed"
    )
    reviewer_comment = Column(
        Text,
        nullable=True,
        comment="Supervisor review comments or feedback"
    )
    
    # Relationships
    student = relationship(
        "User",
        foreign_keys=[student_id]
    )
    placement = relationship("IndustrialPlacement")
    reviewer = relationship(
        "User",
        foreign_keys=[reviewer_id]
    )
    
    # Composite indexes for common queries
    __table_args__ = (
        Index('idx_student_date', 'student_id', 'log_date'),
        Index('uq_daily_logs_student_date', 'student_id', 'log_date', unique=True),
        Index('idx_student_week', 'student_id', 'week_number'),
        Index('idx_status_reviewed', 'status', 'reviewed_at'),
        Index('idx_placement_date', 'placement_id', 'log_date'),
    )
