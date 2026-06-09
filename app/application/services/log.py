"""Log management service for daily log operations.

This module provides services for creating, retrieving, and managing daily logs
with geofence validation and week number calculation.

Example:
    >>> from app.application.services.log import LogService
    >>> 
    >>> with get_db() as db:
    ...     service = LogService(db)
    ...     log = service.create_log(
    ...         student_id=student.id,
    ...         placement_id=placement.id,
    ...         log_date=date.today(),
    ...         activities="Worked on database design",
    ...         latitude=6.5244,
    ...         longitude=3.3792
    ...     )
"""

from typing import Optional, List, Dict, Any
from datetime import date, datetime
import uuid
from sqlalchemy.orm import Session

from app.domain.models.log import DailyLog, LogStatus
from app.domain.models.user import StudentProfile
from app.infrastructure.repositories.log import LogRepository
from app.infrastructure.repositories.placement import PlacementRepository
from app.infrastructure.services.geofence import GeofenceService


class LogService:
    """Service for daily log management.
    
    Provides methods for creating, retrieving, and managing daily logs
    with automatic geofence validation and week number calculation.
    
    Attributes:
        db: Database session for queries
        log_repo: Log repository for data access
        placement_repo: Placement repository for geofence access
        geofence_service: Geofence validation service
    
    Example:
        >>> service = LogService(db)
        >>> log = service.create_log(...)
    """
    
    def __init__(self, db: Session):
        """Initialize the log service.
        
        Args:
            db: Database session for queries
        """
        self.db = db
        self.log_repo = LogRepository(db)
        self.placement_repo = PlacementRepository(db)
        self.geofence_service = GeofenceService()
    
    def create_log(
        self,
        student_id: str,
        placement_id: str,
        log_date: date,
        activity_description: str,
        latitude: float,
        longitude: float,
        client_uuid: Optional[str] = None,
        skills_learned: Optional[str] = None,
        challenges: Optional[str] = None,
        created_offline_at: Optional[datetime] = None
    ) -> DailyLog:
        """Create a new daily log with geofence validation.
        
        Args:
            student_id: Student's user ID
            placement_id: Placement ID
            log_date: Date of the log
            activity_description: Description of activities performed
            latitude: GPS latitude where log was created
            longitude: GPS longitude where log was created
            client_uuid: Optional client-generated UUID for offline sync
            skills_learned: Optional skills learned description
            challenges: Optional challenges faced description
        
        Returns:
            The created DailyLog instance
        
        Raises:
            ValueError: If placement not found or validation fails
        
        Example:
            >>> log = service.create_log(
            ...     student_id=student.id,
            ...     placement_id=placement.id,
            ...     log_date=date.today(),
            ...     activity_description="Worked on API development",
            ...     latitude=6.5244,
            ...     longitude=3.3792
            ... )
        """
        # Ensure a UUID exists (required by model and used for idempotency).
        if not client_uuid:
            client_uuid = str(uuid.uuid4())

        # Check for duplicate client_uuid (offline sync idempotency)
        if client_uuid:
            existing_log = self.log_repo.get_by_client_uuid(client_uuid)
            if existing_log:
                return existing_log

        existing_day_log = self.log_repo.get_log_by_date(student_id, log_date)
        if existing_day_log:
            return existing_day_log
        
        # Get placement with geofence
        placement = self.placement_repo.get_placement_with_geofence(placement_id)
        
        if not placement:
            raise ValueError("Placement not found")
        
        # Validate coordinates
        if not self.geofence_service.validate_coordinates(latitude, longitude):
            raise ValueError("Invalid GPS coordinates")
        
        # Calculate week number
        week_number = self._calculate_week_number(log_date, student_id)
        
        if week_number < 1 or week_number > 25:
            raise ValueError(f"Log date is outside SIWES period (week {week_number})")
        
        # Determine location status and measured distance from geofence center.
        distance_from_geofence = None
        if placement.geofence:
            distance_from_geofence, _ = self.geofence_service.calculate_distance_from_geofence(
                latitude=latitude,
                longitude=longitude,
                geofence=placement.geofence,
            )

        location_status = self.geofence_service.get_location_status(
            latitude=latitude,
            longitude=longitude,
            geofence=placement.geofence
        )
        
        # Prepare log data
        log_data = {
            "student_id": student_id,
            "placement_id": placement_id,
            "log_date": log_date,
            "week_number": week_number,
            "activity_description": activity_description,
            "latitude": latitude,
            "longitude": longitude,
            "distance_from_geofence": distance_from_geofence,
            "location_status": location_status,
            "status": LogStatus.PENDING_REVIEW,
            "created_offline_at": created_offline_at,
            "synced_at": datetime.utcnow(),
            "client_uuid": client_uuid
        }
        
        # Create log
        log = self.log_repo.create(log_data)
        
        return log
    
    def get_student_logs(
        self,
        student_id: str,
        placement_id: Optional[str] = None,
        limit: Optional[int] = None
    ) -> List[DailyLog]:
        """Get all logs for a student.
        
        Args:
            student_id: Student's user ID
            placement_id: Optional placement ID to filter by
            limit: Maximum number of logs to return
        
        Returns:
            List of DailyLog instances
        
        Example:
            >>> logs = service.get_student_logs(student_id, limit=20)
        """
        return self.log_repo.get_student_logs(student_id, placement_id, limit)
    
    def get_logs_by_week(
        self,
        placement_id: str,
        week_number: int
    ) -> List[DailyLog]:
        """Get all logs for a specific week.
        
        Args:
            placement_id: Placement ID
            week_number: Week number (1-25)
        
        Returns:
            List of DailyLog instances for the week
        
        Example:
            >>> week_1_logs = service.get_logs_by_week(placement_id, 1)
        """
        if week_number < 1 or week_number > 25:
            raise ValueError("Week number must be between 1 and 25")
        
        return self.log_repo.get_logs_by_week(placement_id, week_number)
    
    def get_log_by_id(self, log_id: str) -> Optional[DailyLog]:
        """Get a log by its ID.
        
        Args:
            log_id: Log's unique identifier
        
        Returns:
            DailyLog instance, or None if not found
        
        Example:
            >>> log = service.get_log_by_id(log_id)
        """
        return self.log_repo.get_by_id(log_id)
    
    def update_log(
        self,
        log_id: str,
        updates: Dict[str, Any]
    ) -> Optional[DailyLog]:
        """Update a log's content.
        
        Args:
            log_id: Log's unique identifier
            updates: Dictionary of fields to update
        
        Returns:
            Updated DailyLog instance, or None if not found
        
        Raises:
            ValueError: If trying to update a verified log
        
        Example:
            >>> log = service.update_log(
            ...     log_id=log.id,
            ...     updates={"activity_description": "Updated activities"}
            ... )
        """
        # Get existing log
        log = self.log_repo.get_by_id(log_id)
        
        if not log:
            return None
        
        # Prevent updates to verified logs
        if log.status == LogStatus.VERIFIED:
            raise ValueError("Cannot update a verified log")
        
        # Update log
        return self.log_repo.update(log_id, updates)
    
    def delete_log(self, log_id: str) -> bool:
        """Soft delete a log.
        
        Args:
            log_id: Log's unique identifier
        
        Returns:
            True if deleted, False if not found
        
        Raises:
            ValueError: If trying to delete a verified log
        
        Example:
            >>> service.delete_log(log_id)
        """
        # Get existing log
        log = self.log_repo.get_by_id(log_id)
        
        if not log:
            return False
        
        # Prevent deletion of verified logs
        if log.status == LogStatus.VERIFIED:
            raise ValueError("Cannot delete a verified log")
        
        return self.log_repo.delete(log_id, soft=True)
    
    def get_week_summary(self, placement_id: str) -> Dict[int, int]:
        """Get a summary of log counts for each week.
        
        Args:
            placement_id: Placement ID
        
        Returns:
            Dictionary mapping week numbers to log counts
        
        Example:
            >>> summary = service.get_week_summary(placement_id)
            >>> print(f"Week 1: {summary.get(1, 0)} logs")
        """
        return self.log_repo.count_logs_by_week(placement_id)
    
    def _calculate_week_number(
        self,
        log_date: date,
        student_id: str
    ) -> int:
        """Calculate the week number for a log date.
        
        Args:
            log_date: Date of the log
            student_id: Student user ID
        
        Returns:
            Week number (1-25)
        
        Note:
            - Week 1 starts on student's SIWES start date
            - Each week is 7 days
            - Returns week number even if outside valid range
        """
        profile = self.db.query(StudentProfile).filter(
            StudentProfile.user_id == student_id
        ).first()
        if not profile:
            raise ValueError("Student profile not found")
        days_since_start = (log_date - profile.siwes_start_date).days
        week_number = (days_since_start // 7) + 1
        
        return week_number
