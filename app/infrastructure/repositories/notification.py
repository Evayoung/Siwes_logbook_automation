"""Notification repository for notification operations.

This module provides repository methods for Notification model with support
for type filtering and bulk operations.

Example:
    >>> from app.infrastructure.repositories.notification import NotificationRepository
    >>> 
    >>> repo = NotificationRepository(db)
    >>> notifications = repo.get_user_notifications(user_id, unread_only=True)
    >>> repo.mark_all_as_read(user_id)
"""

from typing import List, Optional
from sqlalchemy.orm import Session

from app.infrastructure.repositories.base import BaseRepository
from app.domain.models.chat import Notification, NotificationType


class NotificationRepository(BaseRepository[Notification]):
    """Repository for Notification model operations.
    
    Extends BaseRepository with notification-specific queries including
    type filtering, unread tracking, and bulk operations.
    
    Example:
        >>> repo = NotificationRepository(db)
        >>> notifications = repo.get_user_notifications(user_id)
    """
    
    def __init__(self, db: Session):
        """Initialize the notification repository.
        
        Args:
            db: The database session for queries
        """
        super().__init__(Notification, db)
    
    def get_user_notifications(
        self,
        user_id: str,
        unread_only: bool = False,
        limit: int = 50
    ) -> List[Notification]:
        """Get all notifications for a user.
        
        Args:
            user_id: The user's ID
            unread_only: Whether to return only unread notifications
            limit: Maximum number of notifications to return
        
        Returns:
            List of Notification instances ordered by creation time descending
        
        Example:
            >>> notifications = repo.get_user_notifications(
            ...     user_id,
            ...     unread_only=True
            ... )
        """
        query = self.db.query(Notification).filter(
            Notification.user_id == user_id
        )
        
        if unread_only:
            query = query.filter(Notification.is_read == False)
        
        return query.order_by(
            Notification.created_at.desc()
        ).limit(limit).all()
    
    def get_by_type(
        self,
        user_id: str,
        notification_type: NotificationType,
        limit: int = 20
    ) -> List[Notification]:
        """Get notifications filtered by type.
        
        Args:
            user_id: The user's ID
            notification_type: The notification type to filter by
            limit: Maximum number of notifications to return
        
        Returns:
            List of Notification instances
        
        Example:
            >>> log_notifications = repo.get_by_type(
            ...     user_id,
            ...     NotificationType.LOG_REVIEWED
            ... )
        """
        return self.db.query(Notification).filter(
            Notification.user_id == user_id,
            Notification.type == notification_type
        ).order_by(Notification.created_at.desc()).limit(limit).all()
    
    def count_unread(self, user_id: str) -> int:
        """Count unread notifications for a user.
        
        Args:
            user_id: The user's ID
        
        Returns:
            Number of unread notifications
        
        Example:
            >>> count = repo.count_unread(user_id)
            >>> print(f"You have {count} unread notifications")
        """
        return self.db.query(Notification).filter(
            Notification.user_id == user_id,
            Notification.is_read == False
        ).count()
    
    def mark_as_read(self, notification_ids: List[str]) -> int:
        """Mark notifications as read.
        
        Args:
            notification_ids: List of notification IDs to mark as read
        
        Returns:
            Number of notifications updated
        
        Example:
            >>> updated = repo.mark_as_read([notif1.id, notif2.id])
        """
        result = self.db.query(Notification).filter(
            Notification.id.in_(notification_ids)
        ).update(
            {"is_read": True},
            synchronize_session=False
        )
        self.db.flush()
        return result
    
    def mark_all_as_read(self, user_id: str) -> int:
        """Mark all notifications as read for a user.
        
        Args:
            user_id: The user's ID
        
        Returns:
            Number of notifications updated
        
        Example:
            >>> updated = repo.mark_all_as_read(user_id)
            >>> print(f"Marked {updated} notifications as read")
        """
        result = self.db.query(Notification).filter(
            Notification.user_id == user_id,
            Notification.is_read == False
        ).update(
            {"is_read": True},
            synchronize_session=False
        )
        self.db.flush()
        return result
    
    def delete_old_notifications(
        self,
        user_id: str,
        days: int = 30
    ) -> int:
        """Soft delete notifications older than specified days.
        
        Args:
            user_id: The user's ID
            days: Number of days to keep (default: 30)
        
        Returns:
            Number of notifications deleted
        
        Example:
            >>> deleted = repo.delete_old_notifications(user_id, days=60)
            >>> print(f"Deleted {deleted} old notifications")
        """
        from datetime import datetime, timedelta
        
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        notifications = self.db.query(Notification).filter(
            Notification.user_id == user_id,
            Notification.created_at < cutoff_date
        ).all()
        
        count = 0
        for notification in notifications:
            self.db.delete(notification)
            count += 1
        
        self.db.flush()
        return count
