"""Geofence validation and distance calculation service.

This module provides utilities for validating GPS coordinates against geofence
boundaries using the Haversine formula for accurate distance calculations.

Example:
    >>> from app.infrastructure.services.geofence import GeofenceService
    >>> from app.domain.models.placement import Geofence
    >>> 
    >>> service = GeofenceService()
    >>> is_within = service.is_within_geofence(
    ...     latitude=6.5244,
    ...     longitude=3.3792,
    ...     geofence=geofence
    ... )
"""

import math
from typing import Tuple

from app.domain.models.placement import Geofence
from app.domain.models.log import LocationStatus


class GeofenceService:
    """Service for geofence validation and distance calculations.
    
    Provides methods to validate GPS coordinates against geofence boundaries
    and calculate distances using the Haversine formula.
    
    Example:
        >>> service = GeofenceService()
        >>> distance = service.calculate_distance(
        ...     lat1=6.5244, lon1=3.3792,
        ...     lat2=6.5300, lon2=3.3800
        ... )
        >>> print(f"Distance: {distance:.2f} meters")
    """
    
    # Earth's radius in meters
    EARTH_RADIUS_METERS = 6371000
    
    @staticmethod
    def calculate_distance(
        lat1: float,
        lon1: float,
        lat2: float,
        lon2: float
    ) -> float:
        """Calculate distance between two GPS coordinates using Haversine formula.
        
        The Haversine formula calculates the great-circle distance between two
        points on a sphere given their longitudes and latitudes.
        
        Args:
            lat1: Latitude of first point in decimal degrees
            lon1: Longitude of first point in decimal degrees
            lat2: Latitude of second point in decimal degrees
            lon2: Longitude of second point in decimal degrees
        
        Returns:
            Distance in meters
        
        Example:
            >>> service = GeofenceService()
            >>> # Distance from Lagos to Ibadan (approximately)
            >>> distance = service.calculate_distance(
            ...     lat1=6.5244, lon1=3.3792,  # Lagos
            ...     lat2=7.3775, lon2=3.9470   # Ibadan
            ... )
            >>> print(f"{distance / 1000:.2f} km")
            ~95.00 km
        
        Note:
            - Assumes Earth is a perfect sphere (good approximation for short distances)
            - Accuracy decreases for very long distances
            - Returns 0 if coordinates are identical
        """
        # Convert latitude and longitude to radians
        lat1_rad = math.radians(lat1)
        lon1_rad = math.radians(lon1)
        lat2_rad = math.radians(lat2)
        lon2_rad = math.radians(lon2)
        
        # Haversine formula
        dlat = lat2_rad - lat1_rad
        dlon = lon2_rad - lon1_rad
        
        a = (
            math.sin(dlat / 2) ** 2 +
            math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon / 2) ** 2
        )
        c = 2 * math.asin(math.sqrt(a))
        
        # Calculate distance
        distance = GeofenceService.EARTH_RADIUS_METERS * c
        return distance
    
    def is_within_geofence(
        self,
        latitude: float | None,
        longitude: float | None,
        geofence: Geofence | None
    ) -> bool:
        """Check if a GPS coordinate is within a geofence boundary.
        
        Args:
            latitude: Latitude of the point to check
            longitude: Longitude of the point to check
            geofence: The Geofence object defining the boundary
        
        Returns:
            True if the point is within the geofence, False otherwise
        
        Example:
            >>> geofence = Geofence(
            ...     center_latitude=6.5244,
            ...     center_longitude=3.3792,
            ...     radius_meters=500
            ... )
            >>> service = GeofenceService()
            >>> is_within = service.is_within_geofence(
            ...     latitude=6.5250,
            ...     longitude=3.3800,
            ...     geofence=geofence
            ... )
        
        Note:
            - Returns False if geofence is None
            - Uses Haversine formula for accurate distance calculation
        """
        if not geofence or latitude is None or longitude is None:
            return False
        
        try:
            distance = self.calculate_distance(
                lat1=float(latitude),
                lon1=float(longitude),
                lat2=geofence.latitude,
                lon2=geofence.longitude
            )
            return distance <= geofence.radius_meters
        except (ValueError, TypeError):
            return False
    
    def get_location_status(
        self,
        latitude: float | None,
        longitude: float | None,
        geofence: Geofence | None
    ) -> LocationStatus:
        """Determine the location status for a GPS coordinate.
        
        Args:
            latitude: Latitude of the point to check
            longitude: Longitude of the point to check
            geofence: The Geofence object, or None if not defined
        
        Returns:
            LocationStatus enum value (WITHIN, OUTSIDE, or UNKNOWN)
        
        Example:
            >>> status = service.get_location_status(
            ...     latitude=6.5250,
            ...     longitude=3.3800,
            ...     geofence=geofence
            ... )
            >>> if status == LocationStatus.OUTSIDE:
            ...     print("Warning: Log created outside geofence!")
        
        Note:
            - Returns UNKNOWN if geofence is None
            - Returns UNKNOWN if coordinates are invalid (0, 0)
        """
        # Check for missing coordinates
        if latitude is None or longitude is None:
            return LocationStatus.UNKNOWN
            
        # Check for invalid coordinates
        if latitude == 0 and longitude == 0:
            return LocationStatus.UNKNOWN
        
        # Check if geofence exists
        if not geofence:
            return LocationStatus.UNKNOWN
        
        # Check if within geofence
        if self.is_within_geofence(latitude, longitude, geofence):
            return LocationStatus.WITHIN
        else:
            return LocationStatus.OUTSIDE
    
    def calculate_distance_from_geofence(
        self,
        latitude: float | None,
        longitude: float | None,
        geofence: Geofence | None
    ) -> Tuple[float, bool]:
        """Calculate distance from a point to the geofence center.
        
        Args:
            latitude: Latitude of the point
            longitude: Longitude of the point
            geofence: The Geofence object
        
        Returns:
            Tuple of (distance_in_meters, is_within_boundary)
        
        Example:
            >>> distance, is_within = service.calculate_distance_from_geofence(
            ...     latitude=6.5250,
            ...     longitude=3.3800,
            ...     geofence=geofence
            ... )
            >>> if not is_within:
            ...     print(f"You are {distance:.0f}m from the work site")
        
        Note:
            - Useful for showing users how far they are from the geofence
            - Can be used to provide feedback in the UI
        """
        if latitude is None or longitude is None or not geofence:
            return 0.0, False
            
        try:
            distance = self.calculate_distance(
                lat1=float(latitude),
                lon1=float(longitude),
                lat2=geofence.latitude,
                lon2=geofence.longitude
            )
            is_within = distance <= geofence.radius_meters
            return distance, is_within
        except (ValueError, TypeError):
            return 0.0, False
    
    @staticmethod
    def validate_coordinates(latitude: float | None, longitude: float | None) -> bool:
        """Validate GPS coordinates.
        
        Args:
            latitude: Latitude to validate
            longitude: Longitude to validate
        
        Returns:
            True if coordinates are valid, False otherwise
        
        Example:
            >>> GeofenceService.validate_coordinates(6.5244, 3.3792)
            True
            >>> GeofenceService.validate_coordinates(100, 200)
            False
        
        Note:
            - Latitude must be between -90 and 90
            - Longitude must be between -180 and 180
        """
        if latitude is None or longitude is None:
            return False
            
        try:
            lat_f = float(latitude)
            lon_f = float(longitude)
            if not (-90 <= lat_f <= 90):
                return False
            if not (-180 <= lon_f <= 180):
                return False
            return True
        except (ValueError, TypeError):
            return False
