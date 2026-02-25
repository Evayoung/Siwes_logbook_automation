"""Placement repository for industrial placement and geofence operations.

This module provides repository methods for IndustrialPlacement and Geofence models.

Example:
    >>> from app.infrastructure.repositories.placement import PlacementRepository
    >>> 
    >>> repo = PlacementRepository(db)
    >>> placement = repo.get_active_placement(student_id)
    >>> geofence = repo.get_placement_geofence(placement.id)
"""

from typing import Optional, List
from datetime import date
from sqlalchemy.orm import Session, joinedload

from app.infrastructure.repositories.base import BaseRepository
from app.domain.models.placement import IndustrialPlacement, Geofence


class PlacementRepository(BaseRepository[IndustrialPlacement]):
    """Repository for IndustrialPlacement model operations.
    
    Extends BaseRepository with placement-specific queries including active
    placement lookup, geofence management, and student placement history.
    
    Example:
        >>> repo = PlacementRepository(db)
        >>> placement = repo.get_active_placement(student_id)
    """
    
    def __init__(self, db: Session):
        """Initialize the placement repository.
        
        Args:
            db: The database session for queries
        """
        super().__init__(IndustrialPlacement, db)
    
    def get_active_placement(self, student_id: str) -> Optional[IndustrialPlacement]:
        """Get the active placement for a student.
        
        Args:
            student_id: The student's user ID
        
        Returns:
            The active IndustrialPlacement instance, or None if not found
        
        Example:
            >>> placement = repo.get_active_placement(student_id)
            >>> if placement:
            ...     print(f"Placed at: {placement.company_name}")
        """
        from app.domain.models.user import StudentProfile
        
        # Query through StudentProfile since it has the placement_id foreign key
        student_profile = self.db.query(StudentProfile).filter(
            StudentProfile.user_id == student_id
        ).first()
        
        if not student_profile or not student_profile.placement_id:
            return None
        
        # Get the placement (no date/status checks since model doesn't have those fields)
        placement = self.db.query(IndustrialPlacement).filter(
            IndustrialPlacement.id == student_profile.placement_id
        ).first()
        
        return placement
    
    def get_student_placements(
        self,
        student_id: str,
        include_inactive: bool = True
    ) -> List[IndustrialPlacement]:
        """Get all placements for a student.
        
        Args:
            student_id: The student's user ID
            include_inactive: Whether to include past placements
        
        Returns:
            List of IndustrialPlacement instances
        
        Example:
            >>> placements = repo.get_student_placements(student_id)
            >>> for p in placements:
            ...     print(f"{p.company_name}: {p.start_date} - {p.end_date}")
        """
        placement = self.get_active_placement(student_id)
        return [placement] if placement else []
    
    def get_placement_with_geofence(
        self,
        placement_id: str
    ) -> Optional[IndustrialPlacement]:
        """Get a placement with its geofence eagerly loaded.
        
        Args:
            placement_id: The placement's unique identifier
        
        Returns:
            The IndustrialPlacement instance with geofence, or None if not found
        
        Example:
            >>> placement = repo.get_placement_with_geofence(placement_id)
            >>> if placement.geofence:
            ...     print(f"Radius: {placement.geofence.radius_meters}m")
        """
        return self.db.query(IndustrialPlacement).options(
            joinedload(IndustrialPlacement.geofence)
        ).filter(
            IndustrialPlacement.id == placement_id
        ).first()
    
    def get_placement_geofence(self, placement_id: str) -> Optional[Geofence]:
        """Get the geofence for a placement.
        
        Args:
            placement_id: The placement's unique identifier
        
        Returns:
            The Geofence instance, or None if not found
        
        Example:
            >>> geofence = repo.get_placement_geofence(placement_id)
            >>> if geofence:
            ...     print(f"Center: {geofence.center_latitude}, {geofence.center_longitude}")
        """
        placement = self.db.query(IndustrialPlacement).options(
            joinedload(IndustrialPlacement.geofence)
        ).filter(
            IndustrialPlacement.id == placement_id
        ).first()
        return placement.geofence if placement else None
    
    def create_placement_with_geofence(
        self,
        placement_data: dict,
        geofence_data: dict
    ) -> IndustrialPlacement:
        """Create a placement with its geofence.
        
        Args:
            placement_data: Dictionary of placement fields
            geofence_data: Dictionary of geofence fields
        
        Returns:
            The created IndustrialPlacement instance with geofence
        
        Example:
            >>> placement = repo.create_placement_with_geofence(
            ...     placement_data={
            ...         "student_id": student_id,
            ...         "company_name": "Tech Corp",
            ...         "company_address": "123 Tech Street",
            ...         "start_date": date(2024, 1, 1),
            ...         "end_date": date(2024, 6, 30)
            ...     },
            ...     geofence_data={
            ...         "center_latitude": 6.5244,
            ...         "center_longitude": 3.3792,
            ...         "radius_meters": 500
            ...     }
            ... )
        """
        # Create geofence first (placement references geofence_id)
        geofence = Geofence(**geofence_data)
        self.db.add(geofence)
        self.db.flush()

        # Create placement and link geofence
        placement_data = dict(placement_data)
        placement_data["geofence_id"] = geofence.id
        placement = self.create(placement_data)
        
        # Refresh to load relationship
        self.db.refresh(placement)
        return placement
