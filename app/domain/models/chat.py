"""Chat and notification models.

Defines entities for real-time communication between students and
supervisors, and system notifications for important events.
"""

import enum
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Boolean, Enum, Index
from sqlalchemy.orm import relationship

from .base import Base, TimestampMixin


class ChatMessage(Base, TimestampMixin):
    """Chat message entity for student-supervisor communication.
    
    Represents a single text message in the real-time chat system.
    Messages are delivered via Server-Sent Events (SSE) and persisted
    for history and offline access.
    
    Attributes:
        id: Unique identifier (UUID).
        sender_id: Foreign key to User who sent the message.
        receiver_id: Foreign key to User who receives the message.
        message_body: Text content of the message.
        is_read: Whether receiver has read the message.
        delivered_at: Timestamp when message was delivered (nullable).
        sender: Related User entity (message sender).
        receiver: Related User entity (message receiver).
    
    Example:
        >>> message = ChatMessage(
        ...     id=str(uuid.uuid4()),
        ...     sender_id=student.id,
        ...     receiver_id=supervisor.id,
        ...     message_body="Can we schedule a call tomorrow?",
        ...     is_read=False
        ... )
        >>> print(f"From: {message.sender.email}")
        From: student@university.edu
    
    Note:
        - Messages are only between student and their assigned supervisor
        - No group chat or multi-party messaging
        - Messages sent offline are queued in IndexedDB and synced later
        - is_read flag updated via SSE acknowledgment
    """
    
    __tablename__ = "chat_messages"
    
    id = Column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        comment="Unique message identifier (UUID)"
    )
    sender_id = Column(
        String(36),
        ForeignKey('users.id'),
        nullable=False,
        index=True,
        comment="Foreign key to user who sent message"
    )
    receiver_id = Column(
        String(36),
        ForeignKey('users.id'),
        nullable=False,
        index=True,
        comment="Foreign key to user who receives message"
    )
    message_body = Column(
        Text,
        nullable=False,
        comment="Text content of the message"
    )
    is_read = Column(
        Boolean,
        default=False,
        nullable=False,
        comment="Whether receiver has read the message"
    )
    delivered_at = Column(
        DateTime,
        nullable=True,
        comment="UTC timestamp when message was delivered"
    )
    
    # Relationships
    sender = relationship(
        "User",
        foreign_keys=[sender_id],
        backref="sent_messages"
    )
    receiver = relationship(
        "User",
        foreign_keys=[receiver_id],
        backref="received_messages"
    )

    __table_args__ = (
        Index('ix_chat_messages_sender_receiver_created', 'sender_id', 'receiver_id', 'created_at'),
        Index('ix_chat_messages_receiver_unread_created', 'receiver_id', 'is_read', 'created_at'),
    )


class NotificationType(enum.Enum):
    """Types of system notifications.
    
    Defines categories of notifications for different events
    that require user attention.
    
    Attributes:
        LOG_REVIEWED: Supervisor reviewed a log entry.
        LOG_FLAGGED: Supervisor flagged a log for issues.
        LOG_VERIFIED: Supervisor verified a log entry.
        DEADLINE_APPROACHING: Log submission deadline approaching.
        CALL_REQUEST: Supervisor requested a video call.
        MESSAGE_RECEIVED: New chat message received.
        SYSTEM_ANNOUNCEMENT: General system announcement.
    """
    LOG_REVIEWED = "log_reviewed"
    LOG_FLAGGED = "log_flagged"
    LOG_VERIFIED = "log_verified"
    DEADLINE_APPROACHING = "deadline_approaching"
    CALL_REQUEST = "call_request"
    MESSAGE_RECEIVED = "message_received"
    SYSTEM_ANNOUNCEMENT = "system_announcement"


class Notification(Base, TimestampMixin):
    """User notification entity.
    
    Represents a system notification for important events that require
    user attention. Notifications are delivered in real-time via SSE
    and displayed in the notification center.
    
    Attributes:
        id: Unique identifier (UUID).
        user_id: Foreign key to User who receives notification.
        type: Type of notification (see NotificationType).
        title: Short notification title.
        message: Detailed notification message.
        is_read: Whether user has read the notification.
        related_log_id: Foreign key to related DailyLog (nullable).
        action_url: URL to navigate when notification is clicked (nullable).
        user: Related User entity.
        related_log: Related DailyLog entity (if applicable).
    
    Example:
        >>> notification = Notification(
        ...     id=str(uuid.uuid4()),
        ...     user_id=student.id,
        ...     type=NotificationType.LOG_VERIFIED,
        ...     title="Log Verified",
        ...     message="Your log for Week 3, Day 5 has been verified",
        ...     is_read=False,
        ...     related_log_id=log.id,
        ...     action_url=f"/student/logs/{log.id}"
        ... )
        >>> print(notification.title)
        Log Verified
    
    Note:
        - Notifications are user-specific (no broadcast notifications)
        - Unread notifications show badge count in sidebar
        - Clicking notification marks it as read and navigates to action_url
        - Old notifications auto-deleted after 30 days (configurable)
    """
    
    __tablename__ = "notifications"
    
    id = Column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        comment="Unique notification identifier (UUID)"
    )
    user_id = Column(
        String(36),
        ForeignKey('users.id'),
        nullable=False,
        index=True,
        comment="Foreign key to user who receives notification"
    )
    type = Column(
        Enum(NotificationType),
        nullable=False,
        comment="Type of notification (log_reviewed, deadline, etc.)"
    )
    title = Column(
        String(200),
        nullable=False,
        comment="Short notification title"
    )
    message = Column(
        Text,
        nullable=False,
        comment="Detailed notification message"
    )
    is_read = Column(
        Boolean,
        default=False,
        nullable=False,
        index=True,
        comment="Whether user has read the notification"
    )
    related_log_id = Column(
        String(36),
        ForeignKey('daily_logs.id'),
        nullable=True,
        comment="Foreign key to related log (if applicable)"
    )
    action_url = Column(
        String(500),
        nullable=True,
        comment="URL to navigate when notification is clicked"
    )
    
    # Relationships
    user = relationship("User", backref="notifications")
    related_log = relationship("DailyLog", backref="notifications")

    __table_args__ = (
        Index('ix_notifications_user_unread_created', 'user_id', 'is_read', 'created_at'),
    )


class NotificationBroadcast(Base):
    """Temporary database-backed queue to synchronize events across multiple replicas."""
    
    __tablename__ = "notification_broadcasts"
    
    id = Column(
        Integer,
        primary_key=True,
        autoincrement=True,
        comment="Auto-incrementing broadcast ID"
    )
    user_id = Column(
        String(36),
        nullable=False,
        index=True,
        comment="Recipient user ID"
    )
    event_type = Column(
        String(50),
        nullable=False,
        comment="Type of notification event"
    )
    data = Column(
        Text,
        nullable=False,
        comment="JSON-serialized event payload"
    )
    created_at = Column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
        index=True,
        comment="Timestamp when broadcast was created"
    )

