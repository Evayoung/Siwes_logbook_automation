"""Offline synchronization service for log syncing.

This module provides services for synchronizing offline-created logs from
IndexedDB to the server database with idempotency guarantees.

Example:
    >>> from app.application.services.sync import SyncService
    >>> 
    >>> with get_db() as db:
    ...     service = SyncService(db)
    ...     result = service.sync_logs(student_id, offline_logs)
    ...     print(f"Synced: {result['synced']}, Skipped: {result['skipped']}")
"""

from typing import List, Dict, Any
from datetime import date, datetime
from sqlalchemy.orm import Session

from app.application.services.log import LogService
from app.infrastructure.repositories.log import LogRepository


class SyncService:
    """Service for offline log synchronization.
    
    Provides methods for syncing offline-created logs to the server with
    idempotency guarantees using client_uuid.
    
    Attributes:
        db: Database session for queries
        log_service: Log service for creating logs
        log_repo: Log repository for checking existing logs
    
    Example:
        >>> service = SyncService(db)
        >>> result = service.sync_logs(student_id, offline_logs)
    """
    
    def __init__(self, db: Session):
        """Initialize the sync service.
        
        Args:
            db: Database session for queries
        """
        self.db = db
        self.log_service = LogService(db)
        self.log_repo = LogRepository(db)
    
    def sync_logs(
        self,
        student_id: str,
        offline_logs: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Sync multiple offline logs to the server.
        
        Args:
            student_id: Student's user ID
            offline_logs: List of log dictionaries from IndexedDB
        
        Returns:
            Dictionary containing:
                - synced: Number of logs successfully synced
                - skipped: Number of logs skipped (already exist)
                - failed: Number of logs that failed to sync
                - errors: List of error messages
        
        Example:
            >>> offline_logs = [
            ...     {
            ...         "client_uuid": "offline-uuid-1",
            ...         "placement_id": placement_id,
            ...         "log_date": "2024-01-15",
            ...         "activity_description": "Worked on project",
            ...         "latitude": 6.5244,
            ...         "longitude": 3.3792
            ...     }
            ... ]
            >>> result = service.sync_logs(student_id, offline_logs)
        """
        synced = 0
        skipped = 0
        failed = 0
        errors = []
        
        for log_data in offline_logs:
            try:
                # Check if already synced (idempotency)
                client_uuid = log_data.get("client_uuid")
                
                if client_uuid:
                    existing_log = self.log_repo.get_by_client_uuid(client_uuid)
                    if existing_log:
                        skipped += 1
                        continue
                
                # Parse log date
                log_date_str = log_data.get("log_date")
                if isinstance(log_date_str, str):
                    log_date = date.fromisoformat(log_date_str)
                else:
                    log_date = log_date_str
                
                # Create log
                activity_description = log_data.get("activity_description") or log_data.get("activities")
                if not activity_description:
                    raise ValueError("Missing activity_description")

                self.log_service.create_log(
                    student_id=student_id,
                    placement_id=log_data["placement_id"],
                    log_date=log_date,
                    activity_description=activity_description,
                    latitude=log_data["latitude"],
                    longitude=log_data["longitude"],
                    client_uuid=client_uuid,
                    skills_learned=log_data.get("skills_learned"),
                    challenges=log_data.get("challenges")
                )
                
                synced += 1
                
            except Exception as e:
                failed += 1
                errors.append(f"Failed to sync log {log_data.get('client_uuid', 'unknown')}: {str(e)}")
        
        return {
            "synced": synced,
            "skipped": skipped,
            "failed": failed,
            "errors": errors
        }
    
    def get_unsynced_logs(self, student_id: str) -> List[Dict[str, Any]]:
        """Get all unsynced logs for a student.
        
        This is useful for checking if there are any logs that were created
        on the server but not yet marked as synced.
        
        Args:
            student_id: Student's user ID
        
        Returns:
            List of log dictionaries
        
        Example:
            >>> unsynced = service.get_unsynced_logs(student_id)
            >>> for log in unsynced:
            ...     print(f"Unsynced: {log['log_date']}")
        """
        logs = self.log_repo.get_unsynced_logs(student_id)
        
        return [
            {
                "id": log.id,
                "log_date": log.log_date.isoformat(),
                "activity_description": log.activity_description,
                "client_uuid": log.client_uuid
            }
            for log in logs
        ]
    
    def mark_as_synced(self, log_ids: List[str]) -> int:
        """Mark logs as synced.
        
        Args:
            log_ids: List of log IDs to mark as synced
        
        Returns:
            Number of logs updated
        
        Example:
            >>> count = service.mark_as_synced([log1.id, log2.id])
        """
        count = 0
        
        for log_id in log_ids:
            log = self.log_repo.update(log_id, {"synced_at": datetime.utcnow()})
            if log:
                count += 1
        
        return count
