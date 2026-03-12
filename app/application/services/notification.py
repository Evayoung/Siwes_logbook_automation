"""Notification service for creating and managing notifications.

This module provides services for creating notifications for various events
and delivering them to users.

Example:
    >>> from app.application.services.notification import NotificationService
    >>> 
    >>> with get_db() as db:
    ...     service = NotificationService(db)
    ...     service.notify_log_reviewed(
    ...         student_id=student.id,
    ...         log_id=log.id,
    ...         status="verified"
    ...     )
"""

from typing import List, Optional
from sqlalchemy.orm import Session

from app.domain.models.chat import Notification, NotificationType
from app.domain.models.user import StudentProfile
from app.infrastructure.repositories.notification import NotificationRepository


class NotificationService:
    """Service for notification management.
    
    Provides methods for creating, retrieving, and managing notifications
    for various system events.
    
    Attributes:
        db: Database session for queries
        notification_repo: Notification repository for data access
    
    Example:
        >>> service = NotificationService(db)
        >>> service.notify_log_reviewed(student_id, log_id, "verified")
    """
    
    def __init__(self, db: Session):
        """Initialize the notification service.
        
        Args:
            db: Database session for queries
        """
        self.db = db
        self.notification_repo = NotificationRepository(db)
    
    def create_notification(
        self,
        user_id: str,
        notification_type: NotificationType,
        title: str,
        message: str,
        related_log_id: Optional[str] = None,
        action_url: Optional[str] = None
    ) -> Optional[Notification]:
        """Create a new notification.
        
        Args:
            user_id: User's ID to notify
            notification_type: Type of notification
            title: Notification title
            message: Notification message
            related_log_id: Optional related log ID
            action_url: Optional URL for action button
        
        Returns:
            Created Notification instance
        
        Example:
            >>> notification = service.create_notification(
            ...     user_id=student.id,
            ...     notification_type=NotificationType.LOG_REVIEWED,
            ...     title="Log Reviewed",
            ...     message="Your log for Week 1, Day 3 has been verified",
            ...     related_log_id=log.id,
            ...     action_url=f"/logs/{log.id}"
            ... )
        """
        student_profile = self.db.query(StudentProfile).filter(StudentProfile.user_id == user_id).first()
        if student_profile and not bool(getattr(student_profile, "setting_notifications", True)):
            return None

        notification_data = {
            "user_id": user_id,
            "type": notification_type,
            "title": title,
            "message": message,
            "related_log_id": related_log_id,
            "action_url": action_url,
            "is_read": False
        }
        
        return self.notification_repo.create(notification_data)
    
    def notify_log_reviewed(
        self,
        student_id: str,
        log_id: str,
        status: str,
        feedback: Optional[str] = None
    ) -> Optional[Notification]:
        """Notify student that their log has been reviewed.
        
        Args:
            student_id: Student's user ID
            log_id: Log ID that was reviewed
            status: Review status (verified/flagged)
            feedback: Optional supervisor feedback
        
        Returns:
            Created Notification instance
        
        Example:
            >>> service.notify_log_reviewed(
            ...     student_id=student.id,
            ...     log_id=log.id,
            ...     status="verified",
            ...     feedback="Great work!"
            ... )
        """
        if status == "verified":
            notification_type = NotificationType.LOG_VERIFIED
            title = "Log Verified"
            message = "Your log has been verified by your supervisor"
        else:
            notification_type = NotificationType.LOG_FLAGGED
            title = "Log Flagged"
            message = "Your log has been flagged for review"
        
        if feedback:
            message += f": {feedback}"
        
        return self.create_notification(
            user_id=student_id,
            notification_type=notification_type,
            title=title,
            message=message,
            related_log_id=log_id,
            action_url=f"/logs/{log_id}"
        )
    
    def notify_deadline_approaching(
        self,
        student_id: str,
        week_number: int,
        days_remaining: int
    ) -> Optional[Notification]:
        """Notify student of approaching deadline.
        
        Args:
            student_id: Student's user ID
            week_number: Week number approaching deadline
            days_remaining: Days remaining until deadline
        
        Returns:
            Created Notification instance
        
        Example:
            >>> service.notify_deadline_approaching(
            ...     student_id=student.id,
            ...     week_number=5,
            ...     days_remaining=2
            ... )
        """
        return self.create_notification(
            user_id=student_id,
            notification_type=NotificationType.DEADLINE_APPROACHING,
            title="Deadline Approaching",
            message=f"Week {week_number} deadline is in {days_remaining} days",
            action_url="/logbook"
        )
    
    def notify_call_request(
        self,
        user_id: str,
        from_user_name: str,
        room_url: str
    ) -> Optional[Notification]:
        """Notify user of incoming call request.
        
        Args:
            user_id: User's ID to notify
            from_user_name: Name of user requesting call
            room_url: Call room URL
        
        Returns:
            Created Notification instance
        
        Example:
            >>> service.notify_call_request(
            ...     user_id=supervisor.id,
            ...     from_user_name="John Doe",
            ...     room_url="/supervisor/communication?tab=calls"
            ... )
        """
        return self.create_notification(
            user_id=user_id,
            notification_type=NotificationType.CALL_REQUEST,
            title="Incoming Call Request",
            message=f"{from_user_name} is requesting a video call",
            action_url=room_url
        )
    
    def notify_message_received(
        self,
        user_id: str,
        from_user_name: str,
        message_preview: str
    ) -> Optional[Notification]:
        """Notify user of new chat message.
        
        Args:
            user_id: User's ID to notify
            from_user_name: Name of message sender
            message_preview: Preview of the message
        
        Returns:
            Created Notification instance
        
        Example:
            >>> service.notify_message_received(
            ...     user_id=student.id,
            ...     from_user_name="Dr. Jane Smith",
            ...     message_preview="Can we schedule a call tomorrow?"
            ... )
        """
        return self.create_notification(
            user_id=user_id,
            notification_type=NotificationType.MESSAGE_RECEIVED,
            title=f"New message from {from_user_name}",
            message=message_preview[:100],
            action_url="/chat"
        )
    
    def get_user_notifications(
        self,
        user_id: str,
        unread_only: bool = False,
        limit: int = 50
    ) -> List[Notification]:
        """Get notifications for a user.
        
        Args:
            user_id: User's ID
            unread_only: Whether to return only unread notifications
            limit: Maximum number of notifications to return
        
        Returns:
            List of Notification instances
        
        Example:
            >>> notifications = service.get_user_notifications(
            ...     user_id=user.id,
            ...     unread_only=True
            ... )
        """
        return self.notification_repo.get_user_notifications(
            user_id=user_id,
            unread_only=unread_only,
            limit=limit
        )
    
    def mark_as_read(self, notification_ids: List[str]) -> int:
        """Mark notifications as read.
        
        Args:
            notification_ids: List of notification IDs
        
        Returns:
            Number of notifications marked as read
        
        Example:
            >>> count = service.mark_as_read([notif1.id, notif2.id])
        """
        return self.notification_repo.mark_as_read(notification_ids)
    
    def mark_all_as_read(self, user_id: str) -> int:
        """Mark all notifications as read for a user.
        
        Args:
            user_id: User's ID
        
        Returns:
            Number of notifications marked as read
        
        Example:
            >>> count = service.mark_all_as_read(user_id)
        """
        return self.notification_repo.mark_all_as_read(user_id)
    
    def count_unread(self, user_id: str) -> int:
        """Count unread notifications for a user.
        
        Args:
            user_id: User's ID
        
        Returns:
            Number of unread notifications
        
        Example:
            >>> count = service.count_unread(user_id)
        """
        return self.notification_repo.count_unread(user_id)

