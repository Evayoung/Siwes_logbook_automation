"""Review service for supervisor log review operations.

This module provides services for supervisors to review, verify, and flag
student logs.

Example:
    >>> from app.application.services.review import ReviewService
    >>> 
    >>> with get_db() as db:
    ...     service = ReviewService(db)
    ...     service.verify_log(log_id, supervisor_id, "Great work!")
"""

from typing import List, Optional, Dict, Any
from datetime import datetime
from sqlalchemy.orm import Session

from app.domain.models.log import DailyLog, LogStatus
from app.infrastructure.repositories.log import LogRepository


class ReviewService:
    """Service for log review operations.
    
    Provides methods for supervisors to review, verify, flag, and comment
    on student logs.
    
    Attributes:
        db: Database session for queries
        log_repo: Log repository for data access
    
    Example:
        >>> service = ReviewService(db)
        >>> service.verify_log(log_id, supervisor_id)
    """
    
    def __init__(self, db: Session):
        """Initialize the review service.
        
        Args:
            db: Database session for queries
        """
        self.db = db
        self.log_repo = LogRepository(db)
    
    def verify_log(
        self,
        log_id: str,
        supervisor_id: str,
        feedback: Optional[str] = None
    ) -> Optional[DailyLog]:
        """Verify a log as approved.
        
        Args:
            log_id: Log's unique identifier
            supervisor_id: Supervisor's user ID
            feedback: Optional feedback message
        
        Returns:
            Updated DailyLog instance, or None if not found
        
        Raises:
            ValueError: If log is already verified or flagged
        
        Example:
            >>> log = service.verify_log(
            ...     log_id=log.id,
            ...     supervisor_id=supervisor.id,
            ...     feedback="Excellent work on the database design!"
            ... )
        """
        # Get log
        log = self.log_repo.get_by_id(log_id)
        
        if not log:
            return None
        
        # Check current status
        if log.status == LogStatus.VERIFIED:
            raise ValueError("Log is already verified")
        
        if log.status == LogStatus.FLAGGED:
            raise ValueError("Cannot verify a flagged log. Unflag it first.")
        
        # Update log
        updates = {
            "status": LogStatus.VERIFIED,
            "reviewer_id": supervisor_id,
            "reviewed_at": datetime.utcnow(),
            "reviewer_comment": feedback
        }
        
        return self.log_repo.update(log_id, updates)
    
    def flag_log(
        self,
        log_id: str,
        supervisor_id: str,
        reason: str
    ) -> Optional[DailyLog]:
        """Flag a log for issues.
        
        Args:
            log_id: Log's unique identifier
            supervisor_id: Supervisor's user ID
            reason: Reason for flagging
        
        Returns:
            Updated DailyLog instance, or None if not found
        
        Raises:
            ValueError: If log is already verified
        
        Example:
            >>> log = service.flag_log(
            ...     log_id=log.id,
            ...     supervisor_id=supervisor.id,
            ...     reason="Location is outside geofence. Please verify."
            ... )
        """
        # Get log
        log = self.log_repo.get_by_id(log_id)
        
        if not log:
            return None
        
        # Check current status
        if log.status == LogStatus.VERIFIED:
            raise ValueError("Cannot flag a verified log")
        
        # Update log
        updates = {
            "status": LogStatus.FLAGGED,
            "reviewer_id": supervisor_id,
            "reviewed_at": datetime.utcnow(),
            "reviewer_comment": reason
        }
        
        return self.log_repo.update(log_id, updates)
    
    def unflag_log(
        self,
        log_id: str,
        supervisor_id: str
    ) -> Optional[DailyLog]:
        """Remove flag from a log and return to pending review.
        
        Args:
            log_id: Log's unique identifier
            supervisor_id: Supervisor's user ID
        
        Returns:
            Updated DailyLog instance, or None if not found
        
        Example:
            >>> log = service.unflag_log(log_id, supervisor_id)
        """
        # Get log
        log = self.log_repo.get_by_id(log_id)
        
        if not log:
            return None
        
        # Update log
        updates = {
            "status": LogStatus.PENDING_REVIEW,
            "reviewer_id": supervisor_id,
            "reviewed_at": datetime.utcnow()
        }
        
        return self.log_repo.update(log_id, updates)
    
    def bulk_verify_logs(
        self,
        log_ids: List[str],
        supervisor_id: str,
        feedback: Optional[str] = None
    ) -> Dict[str, Any]:
        """Verify multiple logs at once.
        
        Args:
            log_ids: List of log IDs to verify
            supervisor_id: Supervisor's user ID
            feedback: Optional feedback for all logs
        
        Returns:
            Dictionary containing:
                - verified: Number of logs verified
                - failed: Number of logs that failed
                - errors: List of error messages
        
        Example:
            >>> result = service.bulk_verify_logs(
            ...     log_ids=[log1.id, log2.id, log3.id],
            ...     supervisor_id=supervisor.id,
            ...     feedback="All logs approved"
            ... )
        """
        verified = 0
        failed = 0
        errors = []
        
        for log_id in log_ids:
            try:
                self.verify_log(log_id, supervisor_id, feedback)
                verified += 1
            except Exception as e:
                failed += 1
                errors.append(f"Failed to verify log {log_id}: {str(e)}")
        
        return {
            "verified": verified,
            "failed": failed,
            "errors": errors
        }
    
    def get_pending_logs(
        self,
        placement_id: str
    ) -> List[DailyLog]:
        """Get all logs pending review for a placement.
        
        Args:
            placement_id: Placement ID
        
        Returns:
            List of DailyLog instances with PENDING_REVIEW status
        
        Example:
            >>> pending = service.get_pending_logs(placement_id)
            >>> print(f"{len(pending)} logs pending review")
        """
        return self.log_repo.get_pending_logs(placement_id)
    
    def get_flagged_logs(
        self,
        placement_id: str
    ) -> List[DailyLog]:
        """Get all flagged logs for a placement.
        
        Args:
            placement_id: Placement ID
        
        Returns:
            List of DailyLog instances with FLAGGED status
        
        Example:
            >>> flagged = service.get_flagged_logs(placement_id)
        """
        return self.log_repo.get_logs_by_status(placement_id, LogStatus.FLAGGED)
    
    def get_review_statistics(
        self,
        placement_id: str
    ) -> Dict[str, Any]:
        """Get review statistics for a placement.
        
        Args:
            placement_id: Placement ID
        
        Returns:
            Dictionary containing:
                - total_logs: Total number of logs
                - pending: Number of pending logs
                - verified: Number of verified logs
                - flagged: Number of flagged logs
                - review_rate: Percentage of logs reviewed
        
        Example:
            >>> stats = service.get_review_statistics(placement_id)
            >>> print(f"Review rate: {stats['review_rate']:.1f}%")
        """
        # Get all logs
        all_logs = self.log_repo.get_all({"placement_id": placement_id})
        
        # Count by status
        pending = len([l for l in all_logs if l.status == LogStatus.PENDING_REVIEW])
        verified = len([l for l in all_logs if l.status == LogStatus.VERIFIED])
        flagged = len([l for l in all_logs if l.status == LogStatus.FLAGGED])
        
        total = len(all_logs)
        reviewed = verified + flagged
        review_rate = (reviewed / total * 100) if total > 0 else 0
        
        return {
            "total_logs": total,
            "pending": pending,
            "verified": verified,
            "flagged": flagged,
            "review_rate": review_rate
        }
