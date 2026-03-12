"""Card components for displaying stats, logs, and student information.

Provides reusable card wrappers built on Faststrap for consistent
styling across the SIWES application.
"""

from fasthtml.common import *
from faststrap import Card, StatCard, Progress, Icon, Row, Col, Badge
from datetime import date
from typing import Any
from .badges import StatusBadge, LocationBadge


def WeekProgressCard(
    current_week: int,
    total_weeks: int = 25,
    logs_this_week: int = 0,
    last_entry_time: str | None = None
) -> FT:
    """Week progress card showing current week status.
    
    Args:
        current_week: Current week number (1-25)
        total_weeks: Total weeks (default 25)
        logs_this_week: Number of logs created this week
        last_entry_time: Time of last entry (e.g., "Today, 2:30 PM")
    
    Returns:
        Card component with progress bar
    """
    progress_pct = (current_week / total_weeks) * 100
    
    return Card(
        H5(f"Week {current_week} of {total_weeks}", cls="mb-3"),
        Progress(progress_pct, variant="primary", label=f"{progress_pct:.0f}%", cls="mb-3"),
        P(f"{logs_this_week} Days Logged This Week", cls="mb-1 text-muted small"),
        P(
            f"Last Entry: {last_entry_time}" if last_entry_time else "No entries yet",
            cls="mb-0 text-muted small"
        )
    )


def VerificationStatsCards(verified: int, pending: int, flagged: int) -> FT:
    """Verification status stats cards.
    
    Args:
        verified: Number of verified logs
        pending: Number of pending logs
        flagged: Number of flagged logs
    
    Returns:
        Row of stat cards
    """
    return Row(
        Col(
            StatCard(
                title="Verified",
                value=verified,
                icon=Icon("check-circle-fill"),
                variant="success"
            ),
            md=4
        ),
        Col(
            StatCard(
                title="Pending",
                value=pending,
                icon=Icon("clock-fill"),
                variant="warning"
            ),
            md=4
        ),
        Col(
            StatCard(
                title="Flagged",
                value=flagged,
                icon=Icon("exclamation-triangle-fill"),
                variant="danger"
            ),
            md=4
        )
    )


def LogEntryCard(
    log_id: str,
    log_date: date,
    week_number: int,
    day_number: int,
    activities: str,
    status: str,
    location_status: str,
    distance: float | None = None,
    hours_logged: int | None = None
) -> FT:
    """Log entry card for displaying a single log.
    
    Args:
        log_id: Log unique identifier
        log_date: Date of the log
        week_number: Week number (1-25)
        day_number: Day number within week (1-5)
        activities: Activity description (truncated)
        status: Log status (VERIFIED, PENDING_REVIEW, FLAGGED)
        location_status: Location status (WITHIN, OUTSIDE, UNKNOWN)
        distance: Distance from geofence in meters
        hours_logged: Hours logged for the day
    
    Returns:
        Card component
    """
    date_str = log_date.strftime("%A, %b %d, %Y")
    activities_preview = activities[:100] + "..." if len(activities) > 100 else activities
    
    return Card(
        Div(
            # Header
            Div(
                Div(
                    H6(date_str, cls="mb-0"),
                    P(f"Week {week_number} - Day {day_number}", cls="text-muted small mb-0")
                ),
                StatusBadge(status),
                cls="d-flex justify-content-between align-items-start mb-3"
            ),
            
            # Activity preview
            P(f'"{activities_preview}"', cls="fst-italic text-secondary mb-3"),
            
            # Footer
            Div(
                LocationBadge(location_status, distance),
                P(
                    f"{hours_logged} hours logged" if hours_logged else "",
                    cls="mb-0 ms-3 small text-muted"
                ) if hours_logged else "",
                cls="d-flex align-items-center"
            )
        ),
        hx_get="/student/logbook",
        hx_target="body",
        hx_push_url="true",
        cls="mb-3 cursor-pointer hover-shadow"
    )


def StudentCard(
    student_id: str,
    student_name: str,
    matric_number: str,
    last_log_date: str | None = None,
    current_week: int | None = None,
    status: str = "PENDING_REVIEW",
    pending_count: int = 0
) -> FT:
    """Student card for supervisor dashboard.
    
    Args:
        student_id: Student's user ID
        student_name: Student's full name
        matric_number: Matriculation number
        last_log_date: Date of last log submission
        current_week: Current week number
        status: Overall status
        pending_count: Number of pending logs
    
    Returns:
        Card component
    """
    return Card(
        # Header
        Div(
            H6(student_name, cls="mb-1"),
            P(matric_number, cls="text-muted small mb-0"),
            cls="mb-3"
        ),
        
        # Info
        Div(
            P(
                f"Last Log: {last_log_date}" if last_log_date else "No logs yet",
                cls="mb-1 small text-muted"
            ),
            P(
                f"Week {current_week} of 25" if current_week else "Not started",
                cls="mb-2 small text-muted"
            ),
            cls="mb-3"
        ),
        
        # Status and badges
        Div(
            StatusBadge(status),
            Badge(f"{pending_count} pending", variant="warning") if pending_count > 0 else "",
            cls="mb-3 d-flex gap-2"
        ),
        
        # Action buttons
        Div(
            A("View Logs", href="/supervisor/logs", cls="btn btn-sm btn-outline-primary me-2"),
            A("Message", href=f"/supervisor/communication?student_id={student_id}", cls="btn btn-sm btn-outline-secondary"),
            cls="d-flex"
        )
    )


def WeekGridCell(
    week_number: int,
    day_number: int,
    log_date: date | None = None,
    has_log: bool = False,
    log_status: str | None = None,
    log_id: str | None = None
) -> FT:
    """Week grid cell for 25-week logbook view.
    
    Args:
        week_number: Week number (1-25)
        day_number: Day number (1-5, Mon-Fri)
        log_date: Date for this cell
        has_log: Whether a log exists for this day
        log_status: Status if log exists
        log_id: Log ID if exists
    
    Returns:
        Div element for grid cell
    """
    # Determine CSS class based on status
    if not has_log:
        cell_class = "week-cell week-cell-empty"
        icon = ""
    elif log_status == "VERIFIED":
        cell_class = "week-cell week-cell-verified"
        icon = "OK"
    elif log_status == "PENDING_REVIEW":
        cell_class = "week-cell week-cell-pending"
        icon = "PENDING"
    elif log_status == "FLAGGED":
        cell_class = "week-cell week-cell-flagged"
        icon = "FLAG"
    else:
        cell_class = "week-cell week-cell-empty"
        icon = "DRAFT"

    # Day names
    day_names = ["Mon", "Tue", "Wed", "Thu", "Fri"]
    day_name = day_names[day_number - 1] if 1 <= day_number <= 5 else ""
    
    return Div(
        Div(day_name, cls="fw-bold small"),
        Div(icon, cls="fs-4 my-1") if icon else "",
        Div(log_date.strftime("%d") if log_date else "", cls="small"),
        cls=cell_class,
        hx_get="/student/logbook" if has_log and log_id else None,
        hx_target="body" if has_log and log_id else None,
        hx_push_url="true" if has_log and log_id else None,
        style="cursor: pointer;" if has_log else ""
    )



