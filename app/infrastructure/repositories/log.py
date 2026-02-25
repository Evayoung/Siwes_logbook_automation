"""Log repository for daily log operations.

This module provides repository methods for DailyLog model with support for
offline sync, week-based queries, and status filtering.

Example:
    >>> from app.infrastructure.repositories.log import LogRepository
    >>> 
    >>> repo = LogRepository(db)
    >>> logs = repo.get_student_logs_by_week(student_id, week_number=1)
    >>> pending = repo.get_pending_logs(placement_id)
"""

from typing import Optional, List
from datetime import date, datetime
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_

from app.infrastructure.repositories.base import BaseRepository
from app.domain.models.log import DailyLog, LogStatus, LocationStatus


class LogRepository(BaseRepository[DailyLog]):
    """Repository for DailyLog model operations.
    
    Extends BaseRepository with log-specific queries including week-based
    filtering, status filtering, and offline sync support.
    
    Example:
        >>> repo = LogRepository(db)
        >>> logs = repo.get_student_logs(student_id, limit=10)
    """
    
    def __init__(self, db: Session):
        """Initialize the log repository.
        
        Args:
            db: The database session for queries
        """
        super().__init__(DailyLog, db)
    
    def get_student_logs(
        self,
        student_id: str,
        placement_id: Optional[str] = None,
        limit: Optional[int] = None
    ) -> List[DailyLog]:
        """Get all logs for a student.
        
        Args:
            student_id: The student's user ID
            placement_id: Optional placement ID to filter by
            limit: Maximum number of logs to return
        
        Returns:
            List of DailyLog instances ordered by date descending
        
        Example:
            >>> logs = repo.get_student_logs(student_id, limit=20)
        """
        query = self.db.query(DailyLog).filter(
            DailyLog.student_id == student_id
        )
        
        if placement_id:
            query = query.filter(DailyLog.placement_id == placement_id)
        
        query = query.order_by(DailyLog.log_date.desc())
        
        if limit:
            query = query.limit(limit)
        
        return query.all()
    
    def get_logs_by_week(
        self,
        placement_id: str,
        week_number: int
    ) -> List[DailyLog]:
        """Get all logs for a specific week.
        
        Args:
            placement_id: The placement ID
            week_number: The week number (1-25)
        
        Returns:
            List of DailyLog instances for the week
        
        Example:
            >>> week_1_logs = repo.get_logs_by_week(placement_id, week_number=1)
        """
        return self.db.query(DailyLog).filter(
            DailyLog.placement_id == placement_id,
            DailyLog.week_number == week_number
        ).order_by(DailyLog.log_date).all()
    
    def get_logs_by_status(
        self,
        placement_id: str,
        status: LogStatus,
        limit: Optional[int] = None
    ) -> List[DailyLog]:
        """Get logs filtered by status.
        
        Args:
            placement_id: The placement ID
            status: The log status to filter by
            limit: Maximum number of logs to return
        
        Returns:
            List of DailyLog instances with the specified status
        
        Example:
            >>> pending = repo.get_logs_by_status(
            ...     placement_id,
            ...     LogStatus.PENDING_REVIEW
            ... )
        """
        query = self.db.query(DailyLog).filter(
            DailyLog.placement_id == placement_id,
            DailyLog.status == status
        ).order_by(DailyLog.log_date.desc())
        
        if limit:
            query = query.limit(limit)
        
        return query.all()
    
    def get_pending_logs(self, placement_id: str) -> List[DailyLog]:
        """Get all logs pending review for a placement.
        
        Args:
            placement_id: The placement ID
        
        Returns:
            List of DailyLog instances with PENDING_REVIEW status
        
        Example:
            >>> pending = repo.get_pending_logs(placement_id)
        """
        return self.get_logs_by_status(placement_id, LogStatus.PENDING_REVIEW)
    
    def get_log_by_date(
        self,
        student_id: str,
        log_date: date
    ) -> Optional[DailyLog]:
        """Get a log for a specific date.
        
        Args:
            student_id: The student's user ID
            log_date: The date of the log
        
        Returns:
            The DailyLog instance, or None if not found
        
        Example:
            >>> today_log = repo.get_log_by_date(student_id, date.today())
        """
        return self.db.query(DailyLog).filter(
            DailyLog.student_id == student_id,
            DailyLog.log_date == log_date
        ).first()
    
    def get_unsynced_logs(self, student_id: str) -> List[DailyLog]:
        """Get all logs that haven't been synced to the server.
        
        Args:
            student_id: The student's user ID
        
        Returns:
            List of DailyLog instances with synced_at=None
        
        Example:
            >>> unsynced = repo.get_unsynced_logs(student_id)
            >>> for log in unsynced:
            ...     # Sync to server
            ...     log.is_synced = True
        """
        return self.db.query(DailyLog).filter(
            DailyLog.student_id == student_id,
            DailyLog.synced_at.is_(None)
        ).order_by(DailyLog.log_date).all()
    
    def get_by_client_uuid(self, client_uuid: str) -> Optional[DailyLog]:
        """Get a log by its client UUID (for offline sync).
        
        Args:
            client_uuid: The client-generated UUID
        
        Returns:
            The DailyLog instance, or None if not found
        
        Example:
            >>> log = repo.get_by_client_uuid("offline-uuid-123")
            >>> if log:
            ...     print("Log already synced")
        """
        return self.db.query(DailyLog).filter(
            DailyLog.client_uuid == client_uuid
        ).first()
    
    def get_logs_by_location_status(
        self,
        placement_id: str,
        location_status: LocationStatus
    ) -> List[DailyLog]:
        """Get logs filtered by location status.
        
        Args:
            placement_id: The placement ID
            location_status: The location status to filter by
        
        Returns:
            List of DailyLog instances with the specified location status
        
        Example:
            >>> outside_logs = repo.get_logs_by_location_status(
            ...     placement_id,
            ...     LocationStatus.OUTSIDE
            ... )
        """
        return self.db.query(DailyLog).filter(
            DailyLog.placement_id == placement_id,
            DailyLog.location_status == location_status
        ).order_by(DailyLog.log_date.desc()).all()
    
    def count_logs_by_week(self, placement_id: str) -> dict:
        """Count logs for each week in a placement.
        
        Args:
            placement_id: The placement ID
        
        Returns:
            Dictionary mapping week numbers to log counts
        
        Example:
            >>> counts = repo.count_logs_by_week(placement_id)
            >>> print(f"Week 1: {counts.get(1, 0)} logs")
        """
        logs = self.db.query(
            DailyLog.week_number,
            DailyLog.id
        ).filter(
            DailyLog.placement_id == placement_id
        ).all()
        
        counts = {}
        for week_number, _ in logs:
            counts[week_number] = counts.get(week_number, 0) + 1
        
        return counts
