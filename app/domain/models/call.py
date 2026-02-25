"""Call log model for video/voice call tracking.

This module defines the CallLog model for storing video call history
between students and supervisors.
"""

from sqlalchemy import Column, String, DateTime, Integer, Text, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid

from app.infrastructure.database.connection import Base
from app.domain.models.base import TimestampMixin


class CallLog(Base, TimestampMixin):
    """Model for tracking video/voice calls.
    
    Stores metadata about Daily.co video calls between students and supervisors,
    including room details, participants, and call duration.
    
    Attributes:
        id: Unique identifier (UUID)
        room_name: Daily.co room name
        room_url: Full URL to join the room
        student_id: Foreign key to student user
        supervisor_id: Foreign key to supervisor user
        started_at: When the call was initiated
        ended_at: When the call ended (nullable)
        duration_minutes: Calculated call duration
        status: Call status (scheduled, active, completed, cancelled)
    
    Relationships:
        student: Link to User model (student)
        supervisor: Link to User model (supervisor)
    
    Example:
        >>> call = CallLog(
        ...     room_name="siwes-student-supervisor-20240115",
        ...     student_id="student-123",
        ...     supervisor_id="supervisor-456"
        ... )
        >>> db.add(call)
        >>> db.commit()
    """
    
    __tablename__ = "call_logs"
    
    id = Column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        comment="Unique call log identifier (UUID format)"
    )
    room_name = Column(
        String(200),
        nullable=False,
        unique=True,
        index=True,
        comment="Daily.co room name"
    )
    room_url = Column(
        String(500),
        nullable=False,
        comment="Full URL to join the Daily.co room"
    )
    student_id = Column(
        String(36),
        ForeignKey('users.id'),
        nullable=False,
        index=True,
        comment="Foreign key to student user"
    )
    supervisor_id = Column(
        String(36),
        ForeignKey('users.id'),
        nullable=False,
        index=True,
        comment="Foreign key to supervisor user"
    )
    started_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        comment="When the call was initiated"
    )
    ended_at = Column(
        DateTime,
        nullable=True,
        comment="When the call ended"
    )
    duration_minutes = Column(
        Integer,
        nullable=True,
        comment="Call duration in minutes"
    )
    status = Column(
        String(20),
        nullable=False,
        default="ringing",
        comment="Call status: ringing, accepted, declined, missed, active, completed, cancelled"
    )
    notified_at = Column(
        DateTime,
        nullable=True,
        comment="When the recipient was notified of the call"
    )
    call_type = Column(
        String(10),
        nullable=False,
        default="video",
        comment="Call type: video or voice"
    )
    notes = Column(
        Text,
        nullable=True,
        comment="Optional notes about the call"
    )
    
    # Relationships
    student = relationship(
        "User",
        foreign_keys=[student_id],
        backref="student_calls"
    )
    supervisor = relationship(
        "User",
        foreign_keys=[supervisor_id],
        backref="supervisor_calls"
    )
    
    def __repr__(self):
        return f"<CallLog(room={self.room_name}, status={self.status})>"
