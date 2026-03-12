"""Student dashboard components."""

from datetime import datetime
from typing import Any

from fasthtml.common import *
from faststrap import Badge, Button, Card, Col, Icon, Progress, Row


def _status_badge_variant(status: str) -> str:
    status_map = {
        "verified": "success",
        "pending_review": "warning",
        "flagged": "danger",
        "draft": "secondary",
    }
    return status_map.get(status, "secondary")


def _status_label(status: str) -> str:
    labels = {
        "verified": "Verified",
        "pending_review": "Pending",
        "flagged": "Flagged",
        "draft": "Draft",
    }
    return labels.get(status, "Unknown")


def RecentActivityCard(activity: dict[str, Any]) -> FT:
    date_obj = activity.get("date")
    date_label_day = date_obj.strftime("%a") if date_obj else "--"
    date_label_num = str(date_obj.day) if date_obj else "--"

    return Div(
        Div(
            Div(
                Div(date_label_day, cls="text-center fw-bold text-muted"),
                Div(date_label_num, cls="text-center fw-bold fs-5"),
                cls="me-3",
                style="min-width: 50px;",
            ),
            Div(
                P(activity.get("description", ""), cls="mb-1 small"),
                P(
                    f"Week {activity.get('week_number', '--')} - ",
                    Span(activity.get("location_label", "Unknown"), cls="text-muted"),
                    cls="small text-muted mb-0",
                ),
                cls="flex-grow-1",
            ),
            cls="d-flex",
        ),
        Badge(
            _status_label(activity.get("status", "")),
            pill=True,
            variant=_status_badge_variant(activity.get("status", "")),
        ),
        cls="d-flex justify-content-between align-items-center py-3 px-3",
        style="background-color: #f0f0f0; border-radius: 10px;",
    )


def StudentDashboard(
    user_name: str,
    current_week: int = 1,
    verified: int = 0,
    pending: int = 0,
    flagged: int = 0,
    missed: int = 0,
    hours: int = 0,
    completion_percent: int = 0,
    week_progress_percent: int = 0,
    days_logged_this_week: int = 0,
    last_entry_label: str = "No entry yet",
    location_accuracy_percent: int = 0,
    location_within_count: int = 0,
    location_total_count: int = 0,
    recent_activities: list[dict[str, Any]] | None = None,
) -> FT:
    """Student dashboard body (content only)."""

    header = Div(
        Div(
            H2(f"Welcome back, {user_name}!", cls="mb-1"),
            P("Here's an overview of your SIWES progress", cls="text-muted mb-0"),
            cls="flex-grow-1",
        ),
        Button(
            Icon("plus-lg", cls="me-2"),
            "Create Log",
            variant="primary",
            as_="a",
            href="/student/logbook",
            style="width: 150px;",
        ),
        cls="d-flex justify-content-between align-items-start mb-4 gap-3 flex-wrap",
    )

    week_card = Card(
        Div(
            Div(
                Icon("calendar-week", cls="text-primary me-2"),
                f"Week {current_week} of 25",
                cls="d-flex align-items-center mb-2",
            ),
            P(datetime.now().strftime("%B %d, %Y"), cls="text-muted small mb-3"),
            Progress(
                week_progress_percent,
                variant="primary",
                height="8px",
                cls="mb-3",
            ),
            Div(
                Div(
                    Strong(str(days_logged_this_week)),
                    " days logged this week",
                    cls="small text-muted",
                ),
                Div(
                    "Last entry: ",
                    Strong(last_entry_label),
                    cls="small text-muted",
                ),
                cls="d-flex justify-content-between",
            ),
            Div(
                H2(f"{completion_percent}%", cls="mb-0 text-primary"),
                P("Completed", cls="text-muted small mb-2"),
                cls="position-absolute top-0 end-0 m-3 text-end",
            ),
            cls="position-relative",
        ),
        cls="mb-4",
    )

    stats_cards = Row(
        Col(
            Card(
                Div(
                    Div(
                        Icon("check-circle", cls="fs-5 mb-2"),
                        style="background-color: #E7F7F2; border-radius: 10px; padding: 5px 10px; color: #10B77F;",
                    ),
                    Div(
                        H3(str(verified), cls="mb-0"),
                        P("Verified", cls="text-muted small mb-0"),
                        cls="text-left",
                    ),
                    cls="d-flex align-items-center w-100 h-100 gap-3",
                ),
                cls="h-100",
            ),
            md=3,
            sm=6,
            cls="mb-3",
        ),
        Col(
            Card(
                Div(
                    Div(
                        Icon("calendar-x", cls="fs-5 mb-2"),
                        style="background-color: #FFF3CD; border-radius: 10px; padding: 5px 10px; color: #997404;",
                    ),
                    Div(
                        H3(str(missed), cls="mb-0"),
                        P("Missed", cls="text-muted small mb-0"),
                        cls="text-left",
                    ),
                    cls="d-flex align-items-center w-100 h-100 gap-3",
                ),
                cls="h-100",
            ),
            md=3,
            sm=6,
            cls="mb-3",
        ),
        Col(
            Card(
                Div(
                    Div(
                        Icon("clock", cls="fs-5 mb-2"),
                        style="background-color: #FDF5E6; border-radius: 10px; padding: 5px 10px; color: #F8C468;",
                    ),
                    Div(
                        H3(str(pending), cls="mb-0"),
                        P("Pending", cls="text-muted small mb-0"),
                        cls="text-left",
                    ),
                    cls="d-flex align-items-center w-100 h-100 gap-3",
                ),
                cls="h-100",
            ),
            md=3,
            sm=6,
            cls="mb-3",
        ),
        Col(
            Card(
                Div(
                    Div(
                        Icon("exclamation-circle", cls="fs-5 mb-2"),
                        style="background-color: #FDECEC; border-radius: 10px; padding: 5px 10px; color: #EF4343;",
                    ),
                    Div(
                        H3(str(flagged), cls="mb-0"),
                        P("Flagged", cls="text-muted small mb-0"),
                        cls="text-left",
                    ),
                    cls="d-flex align-items-center w-100 h-100 gap-3",
                ),
                cls="h-100",
            ),
            md=3,
            sm=6,
            cls="mb-3",
        ),
        Col(
            Card(
                Div(
                    Div(
                        Icon("hourglass-split", cls="fs-5 mb-2"),
                        style="background-color: #EBF2FE; border-radius: 10px; padding: 5px 10px; color: #3C83F6;",
                    ),
                    Div(
                        H3(str(hours), cls="mb-0"),
                        P("Hours", cls="text-muted small mb-0"),
                        cls="text-left",
                    ),
                    cls="d-flex align-items-center w-100 h-100 gap-3",
                ),
                cls="h-100",
            ),
            md=3,
            sm=6,
            cls="mb-3",
        ),
        cls="g-3",
        cols=2,
        cols_md=3,
        cols_lg=4,
    )

    location_card = Card(
        Div(
            Div(
                H6("Location Accuracy", cls="mb-0"),
                Span(
                    f"{location_accuracy_percent}% proximity score",
                    style="font-size:12px; background-color: #E7F7F2; border-radius: 20px; padding: 4px 8px; color: #10B77F;",
                ),
                cls="d-flex justify-content-between align-items-center mb-3",
            ),
            Div(
                Progress(
                    location_accuracy_percent,
                    variant="primary",
                    height="8px",
                    cls="mb-3 w-100",
                ),
                Icon("activity", cls="text-success"),
                cls="d-flex align-items-center gap-2 w-90 justify-content-between",
            ),
            P(
                f"{location_within_count} of {location_total_count} logs fully within geofence",
                cls="small text-muted mb-0",
            ),
        ),
        cls="mb-4",
    )

    activity_card = Card(
        Div(
            Div(
                H6("Recent Activity", cls="mb-0"),
                A("View all", href="/student/logbook", cls="text-decoration-none small"),
                cls="d-flex justify-content-between align-items-center mb-3",
            ),
            Col(
                *(
                    [RecentActivityCard(activity) for activity in (recent_activities or [])]
                    if (recent_activities or [])
                    else [P("No activity yet. Create your first log entry.", cls="text-muted small mb-0")]
                ),
                cls="activity-list",
            ),
        ),
        cls="mb-4",
    )

    return Div(header, week_card, stats_cards, location_card, activity_card)
