"""Domain models package.

This package contains all SQLAlchemy models representing the core
business entities of the SIWES Logbook System.

Models:
    User: Core authentication entity.
    UserRole: Enumeration of user roles (STUDENT, SUPERVISOR).
    StudentProfile: Extended profile for students.
    SupervisorProfile: Extended profile for supervisors.
    IndustrialPlacement: Company/organization assignment.
    Geofence: Location boundary for validation.
    DailyLog: Daily activity log entry (core entity).
    LogStatus: Enumeration of log lifecycle states.
    LocationStatus: Enumeration of geofence validation results.
    ChatMessage: Real-time chat message.
    Notification: System notification.
    NotificationType: Enumeration of notification types.

Usage:
    >>> from app.domain.models import User, DailyLog, Geofence
    >>> from app.domain.models.base import Base
    >>> 
    >>> # Create database tables
    >>> Base.metadata.create_all(engine)
"""

from .base import Base, TimestampMixin, SoftDeleteMixin
from .user import User, UserRole, StudentProfile, SupervisorProfile
from .placement import IndustrialPlacement, Geofence
from .log import DailyLog, LogStatus, LocationStatus
from .chat import ChatMessage, Notification, NotificationType, NotificationBroadcast
from .call import CallLog

__all__ = [
    # Base classes
    "Base",
    "TimestampMixin",
    "SoftDeleteMixin",
    # User models
    "User",
    "UserRole",
    "StudentProfile",
    "SupervisorProfile",
    # Placement models
    "IndustrialPlacement",
    "Geofence",
    # Log models
    "DailyLog",
    "LogStatus",
    "LocationStatus",
    # Communication models
    "ChatMessage",
    "Notification",
    "NotificationType",
    "NotificationBroadcast",
    "CallLog",
]
