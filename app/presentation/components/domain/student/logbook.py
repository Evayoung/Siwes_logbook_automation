"""Student logbook components - Daily log tracking with 25-week overview."""

from fasthtml.common import *
from faststrap import Card, Button, Icon, Alert, Input, Badge, Modal, Row, Col, ToggleGroup
from datetime import datetime, timedelta
from typing import List, Dict


def FilterTabs(active_filter: str = "all", oob: bool = False) -> FT:
    """Filter tabs for logbook view.
    
    Args:
        active_filter: Current active filter (all, this_week, pending)
        oob: Whether to return as Out-Of-Band swap
    
        
    Returns:
        Filter tabs HTML
    """
    filters = [
        {"key": "all", "label": "All Weeks"},
        {"key": "this_week", "label": "This Week"},
        {"key": "pending", "label": "Pending Review"},
    ]
    
    tabs = ToggleGroup(
        *[
            Button(
                f["label"],
                variant="light",
                cls="comm-view-btn",
                hx_get=f"/student/logbook/filter/{f['key']}",
                hx_target="#weeks-container",
                hx_swap="innerHTML",
                style="max-width: 160px;"
            )
            for f in filters
        ],
        active_index=next((idx for idx, f in enumerate(filters) if f["key"] == active_filter), 0),
        cls="comm-view-toggle d-flex flex-wrap gap-3 mb-4 justify-content-start",
    )
    return Div(
        tabs,
        id="student-filter-tabs",
        hx_swap_oob="true" if oob else None
    )


def DayCell(day_name: str, display_date: str, iso_date: str, status: str | None = None, hours: int | None = None) -> FT:
    """Individual day cell in week card.
    
    Args:
        day_name: Day of week (Mon, Tue, etc.)
        display_date: Date string for display (e.g., "Jan 15")
        iso_date: Date string for logic (YYYY-MM-DD)
        status: Log status (verified, pending, flagged, None)
        hours: Hours logged
    
    Returns:
        Day cell HTML with modal trigger
    """
    status_icons = {
        "verified": Icon("check2-circle", cls="text-success fs-4"),
        "pending": Icon("exclamation-circle", cls="fs-4"),
        "flagged": Icon("x-circle", cls="text-danger fs-4"),
    }
    
    cell_class = f"day-cell day-cell-{status}" if status else "day-cell day-cell-pending"
    
    # Map backend status to UI class if needed
    if status == "pending_review": 
        cell_class = "day-cell day-cell-pending"
        
    icon_key = "pending"
    if status == "verified": icon_key = "verified"
    elif status == "flagged": icon_key = "flagged"
    elif status == "pending_review": icon_key = "pending"
    
    return A(
        Div(
            Div(
                Div(day_name, cls="fw-bold"),
                Icon(status_icons.get(icon_key), cls="fs-5"),
                cls="d-flex justify-content-between align-items-center w-100"
            ),
            P(display_date, style="font-size: 13px; text-align: left; margin-bottom: 0;"),
            Hr(cls="my-2 border-2 w-100"),
            P(f"{hours}h logged" if hours else "0h logged", style="font-size: 13px; text-align: left;  margin-bottom: 0;"),
            cls=f"{cell_class} black-color",
        ),
        data_bs_toggle="modal",
        data_bs_target="#logModal",
        hx_get=f"/student/logbook/day/{iso_date}",
        hx_target="#modal-body-content",
        hx_swap="innerHTML",
        cls="text-decoration-none"
    )

def DayCellNormal(day_name: str, display_date: str, iso_date: str, status: str | None = None) -> FT:
    """Individual day cell in week card (simplified)."""
    cell_class = f"day-cell day-cell-{status}" if status else "day-cell day-cell-pending"
    if status == "pending_review": cell_class = "day-cell day-cell-pending"
    
    return A(
        Div(
            Div(day_name, cls="fw-bold"),
            cls=f"{cell_class} black-color justify-content-center align-items-center w-100",
        ),
        data_bs_toggle="modal",
        data_bs_target="#logModal",
        hx_get=f"/student/logbook/day/{iso_date}",
        hx_target="#modal-body-content",
        hx_swap="innerHTML",
        cls="text-decoration-none"
    )


def WeekCard(
    week_number: int,
    start_date: datetime,
    days_data: List[Dict],
    week_phase: str = "past",
    show_completed_badge: bool = False,
) -> FT:
    """Week card showing 5 daily cells."""
    end_date = start_date + timedelta(days=4)
    date_range = f"{start_date.strftime('%b %d')} - {end_date.strftime('%b %d, %Y')}"
    
    phase = week_phase if week_phase in {"past", "current", "future"} else "past"
    
    return Card(
        # Header
        Div(
            Div(
                H5(f"Week {week_number}", cls="mb-0"),
                P(date_range, cls="text-muted small mb-0"),
                cls="week-card-header-left"
            ),
            Div(
                Badge("Completed Week", variant="secondary", cls="me-1") if show_completed_badge else "",
                Badge("Current Week", variant="primary", cls="me-1") if phase == "current" else "",
                cls="week-card-header-right"
            ),
            cls="week-card-header"
        ),
        
        # Daily grid
        Div(
            *[
                DayCellNormal(
                    day["name"],
                    day["display_date"],
                    day["iso_date"],
                    day.get("status")
                )
                for day in days_data
            ],
            cls="daily-grid m-1"
        ),
        
        cls=f"week-card week-card-{phase} white-color"
    )

# GPS Capture JavaScript
GPS_CAPTURE_SCRIPT = """
if (navigator.geolocation) {
    navigator.geolocation.getCurrentPosition(
        (position) => {
            document.getElementById('latitude').value = position.coords.latitude;
            document.getElementById('longitude').value = position.coords.longitude;
            document.getElementById('gps-coords').textContent = 
                position.coords.latitude.toFixed(6) + ', ' + position.coords.longitude.toFixed(6);
            document.getElementById('gps-status').textContent = 'Location acquired';
            document.getElementById('gps-alert').className = 'alert alert-success';
            document.getElementById('submit-btn').disabled = false;
        },
        (error) => {
            document.getElementById('gps-status').textContent = 'Location required - Please enable GPS';
            document.getElementById('gps-alert').className = 'alert alert-danger';
        }
    );
} else {
    document.getElementById('gps-status').textContent = 'GPS not supported';
    document.getElementById('gps-alert').className = 'alert alert-danger';
}

// Character counter
const textarea = document.querySelector('textarea[name="activity_description"]');
const charCount = document.getElementById('char-count');
if (textarea && charCount) {
    textarea.addEventListener('input', () => {
        charCount.textContent = textarea.value.length;
    });
}
"""

def LogEntryModalBody(date: str, existing_log: Dict | None = None) -> FT:
    """Modal body content.
    Args:
        date: ISO date string (YYYY-MM-DD)
    """
    is_readonly = bool(existing_log and (existing_log.get("status") == "verified" or existing_log.get("readonly")))
    
    return Div(
        # ... GPS Alerts ...
        # (Assuming these are unchanged, focusing on Form)
        Alert(
            Div(
                Icon("geo-alt-fill", cls="me-2"),
                Span("Detecting location...", id="gps-status"),
                cls="d-flex align-items-center"
            ),
            Div(
                "Coordinates: ",
                Span("--", id="gps-coords", cls="font-monospace"),
                cls="small mt-2"
            ),
            variant="info",
            id="gps-alert"
        ) if not existing_log else Alert(
            Div(
                Icon("geo-alt-fill", cls="me-2 text-success"),
                f"Location: {existing_log.get('latitude', 0):.6f}, {existing_log.get('longitude', 0):.6f}",
                cls="d-flex align-items-center"
            ),
            variant="success"
        ),
        Alert(
            existing_log.get("lock_message"),
            variant="warning",
            cls="mb-3",
        ) if existing_log and existing_log.get("lock_message") else "",
        
        # Form
        Form(
            # Date (read-only)
            Input(type="date", name="log_date", label="Date", value=date, readonly=True, cls="mb-3"),
            
            # Activity Description
            Div(
                Label("Activity Description *", cls="form-label"),
                Textarea(
                    existing_log.get("description", "") if existing_log else "",
                    name="activity_description",
                    rows=6,
                    placeholder="Describe your activities for this day..." if not is_readonly else "",
                    required=True,
                    maxlength=500,
                    readonly=is_readonly,
                    cls="form-control"
                ),
                P(
                    Span("0", id="char-count"),
                    " / 500 characters",
                    cls="text-muted small"
                ),
                cls="mb-3"
            ),
            
            # Hidden GPS fields
            Input(
                type="hidden",
                name="latitude",
                id="latitude",
                required=not bool(existing_log),
                value=str(existing_log.get("latitude", "")) if existing_log else "",
            ),
            Input(
                type="hidden",
                name="longitude",
                id="longitude",
                required=not bool(existing_log),
                value=str(existing_log.get("longitude", "")) if existing_log else "",
            ),
            Input(type="hidden", name="log_date", value=date),
            
            # Submit button
            Div(
                Button(
                    "Close",
                    type="button",
                    variant="secondary",
                    data_bs_dismiss="modal",
                    cls="me-2"
                ),
                Button(
                    "Save Log Entry",
                    variant="primary",
                    type="submit",
                    id="submit-btn",
                    disabled=True if not existing_log else False
                ) if not is_readonly else "",
                cls="d-flex justify-content-end"
            ),
            
            # GPS capture script
            Script(GPS_CAPTURE_SCRIPT) if not existing_log else "",
            
            method="post",
            action="/student/logbook/create",
            hx_post="/student/logbook/create",
            hx_target="#modal-body-content",
            hx_swap="outerHTML"
        ),
        
        id="modal-body-content"
    )


def LogAccessBlockedModalBody(message: str) -> FT:
    """Read-only modal body for blocked log dates."""
    return Div(
        Alert(message, variant="warning"),
        Div(
            Button(
                "Close",
                type="button",
                variant="secondary",
                data_bs_dismiss="modal",
            ),
            cls="d-flex justify-content-end",
        ),
        id="modal-body-content",
    )


def LogbookPage(
    weeks_data: List[Dict],
    current_week: int,
    total_weeks: int = 25,
    offline_mode_enabled: bool = True,
) -> FT:
    """Main logbook page with week cards.
    
    Args:
        weeks_data: List of week data
        current_week: Current week number
        total_weeks: Total weeks (default 25)
    
    Returns:
        Complete logbook page
    """
    return Div(
        # Header
        Div(
            Div(
                H2("Daily Logbook", cls="mb-0"),
                P("25-Week SIWES Program", cls="text-muted"),
                cls="flex-grow-1"
            ),
            Div(
                Button(
                    Icon("arrow-repeat", cls="me-2"),
                    Span("Sync Pending", cls="me-2"),
                    Span("0", id="offline-sync-count", cls="badge text-bg-light d-none"),
                    variant="light",
                    cls="border",
                    id="offline-sync-btn",
                    type="button",
                ),
                Button(
                    Icon("plus-lg", cls="me-2"),
                    "New Log Entry",
                    variant="primary",
                    data_bs_toggle="modal",
                    data_bs_target="#logModal",
                    hx_get="/student/logbook/day/today",
                    hx_target="#modal-body-content",
                    hx_swap="innerHTML",
                    style="width: 200px;"
                ),
                cls="d-flex align-items-center gap-2",
            ),
            cls="d-flex justify-content-between align-items-start mb-4 gap-3 flex-wrap",
        ),
        Div(
            Icon("geo-alt-fill", cls="me-2"),
            Span("GPS is off or unavailable. Please enable location before submitting today's log."),
            cls="alert alert-warning d-none align-items-center",
            id="logbook-gps-warning",
        ),
        Alert(
            Div(
                Icon("wifi", cls="me-2"),
                "Offline mode is disabled. Internet connection is required for offline sync features.",
                cls="d-flex align-items-center",
            ),
            variant="warning",
            cls="mb-3",
        ) if not offline_mode_enabled else "",
        
        # Filter tabs
        FilterTabs(),
        
        # Current week indicator
        Card(
            Div(
                H5(f"Week {current_week}", cls="mb-3"),
                Div(
                    Button(
                        Icon("chevron-left"),
                        size="sm",
                        disabled=current_week == 1
                    ),
                    Span(f"{current_week} / {total_weeks}", cls="mx-3"),
                    Button(
                        Icon("chevron-right"),
                        size="sm",
                        disabled=current_week == total_weeks
                    ),
                    cls="d-flex align-items-center justify-content-center mb-4"
                ),
                cls="d-flex align-items-center justify-content-between"
            ),
            Div(
                *[
                    DayCell(
                        day["name"],
                        day["display_date"],
                        day["iso_date"],
                        day.get("status"),
                        day.get("hours")
                    )
                    for day in (
                        next((w["days"] for w in weeks_data if w.get("number") == current_week), None)
                        or (weeks_data[0]["days"] if weeks_data else [])
                    )
                ],
                cls="daily-grid"
            ),

            cls="mb-4 white-color"
        ),

        H5("All Weeks Overview", cls="mb-3"),

        # Weeks container
        Div(
            *[
                WeekCard(
                    week["number"],
                    week["start_date"],
                    week["days"],
                    week_phase=week.get("phase", "past"),
                    show_completed_badge=bool(week.get("show_completed_badge", False)),
                )
                for week in weeks_data
            ],
            id="weeks-container",
        ),
        
        # Proper Faststrap Modal component
        Modal(
            Div(id="modal-body-content"),  # Dynamic content loaded by HTMX
            modal_id="logModal",
            title="Log Entry",
            centered=True,
            size="lg"
        ),
        Script("""
            (function() {
                const banner = document.getElementById('logbook-gps-warning');
                if (!banner) return;
                const show = () => banner.classList.remove('d-none');
                const hide = () => banner.classList.add('d-none');

                if (!navigator.geolocation) {
                    show();
                    return;
                }

                if (navigator.permissions && navigator.permissions.query) {
                    navigator.permissions.query({ name: 'geolocation' }).then((result) => {
                        if (result.state === 'granted') hide();
                        else show();
                        result.onchange = function () {
                            if (result.state === 'granted') hide();
                            else show();
                        };
                    }).catch(show);
                } else {
                    navigator.geolocation.getCurrentPosition(
                        function() { hide(); },
                        function() { show(); },
                        { timeout: 2000 }
                    );
                }
            })();
        """),
        Div(
            "",
            id="offline-sync-config",
            data_offline_mode="1" if offline_mode_enabled else "0",
            cls="d-none",
        ),
        Script(src="/assets/offline_log_sync.js?v=20260226-2"),
    )


