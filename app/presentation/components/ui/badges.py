"""Badge components for status and location indicators.

Provides consistent badge styling for log statuses, location verification,
and other status indicators throughout the SIWES application.
"""

from fasthtml.common import *
from faststrap import Badge


def StatusBadge(status: str) -> FT:
    """Status badge for log entries.
    
    Args:
        status: Log status (VERIFIED, PENDING_REVIEW, FLAGGED, DRAFT)
    
    Returns:
        Badge component with appropriate variant
    
    Example:
        >>> StatusBadge("VERIFIED")
        <Badge variant="success">Verified</Badge>
    """
    badge_config = {
        "VERIFIED": ("Verified", "success"),
        "PENDING_REVIEW": ("Pending", "warning"),
        "FLAGGED": ("Flagged", "danger"),
        "DRAFT": ("Draft", "secondary")
    }
    
    text, variant = badge_config.get(status, ("Unknown", "secondary"))
    return Badge(text, variant=variant, pill=True)


def LocationBadge(location_status: str, distance: float | None = None) -> FT:
    """Location verification badge.
    
    Args:
        location_status: Location status (WITHIN, OUTSIDE, UNKNOWN)
        distance: Distance from geofence center in meters (optional)
    
    Returns:
        Badge component showing location verification status
    
    Example:
        >>> LocationBadge("WITHIN", 50)
        <Badge variant="success">Within geofence (50m)</Badge>
    """
    if location_status == "WITHIN":
        text = f"Within geofence ({int(distance)}m)" if distance else "Within geofence"
        return Badge(text, variant="success", pill=True)
    elif location_status == "OUTSIDE":
        text = f"Outside boundary ({int(distance)}m)" if distance else "Outside boundary"
        return Badge(text, variant="warning", pill=True)
    else:
        return Badge("Location unknown", variant="secondary", pill=True)


def OnlineBadge(is_online: bool = True, is_syncing: bool = False) -> FT:
    """Online/offline status badge for PWA.
    
    Args:
        is_online: Whether the app is online
        is_syncing: Whether data is currently syncing
    
    Returns:
        Badge component showing connection status
    
    Example:
        >>> OnlineBadge(is_online=True)
        <Badge variant="success">Connected</Badge>
    """
    if is_syncing:
        return Badge(
            Span("Syncing...", cls="d-flex align-items-center gap-2"),
            variant="warning",
            pill=True
        )
    elif is_online:
        return Badge("Connected", variant="success", pill=True)
    else:
        return Badge("Offline Mode", variant="danger", pill=True)


def CountBadge(count: int, variant: str = "primary") -> FT:
    """Count badge for notifications, pending items, etc.
    
    Args:
        count: Number to display
        variant: Bootstrap variant (primary, danger, warning, etc.)
    
    Returns:
        Badge component with count
    
    Example:
        >>> CountBadge(12, "danger")
        <Badge variant="danger">12</Badge>
    """
    return Badge(str(count), variant=variant, pill=True)


