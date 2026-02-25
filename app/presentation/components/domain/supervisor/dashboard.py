"""Supervisor dashboard components."""

from fasthtml.common import *
from faststrap import Alert, Badge, Button, Card, Col, Icon, Row, Table, TBody, TCell, THead, TRow


def SupervisorStatsCard(title: str, value: str, icon: str, color: str) -> FT:
    """Stats card for supervisor dashboard."""
    colors = {
        "purple": ("bg-primary-subtle", "text-primary"),
        "orange": ("bg-warning-subtle", "text-warning"),
        "green": ("bg-success-subtle", "text-success"),
        "red": ("bg-danger-subtle", "text-danger"),
    }
    bg_cls, text_cls = colors.get(color, ("bg-light", "text-dark"))

    return Card(
        Div(
            Div(
                Icon(icon, cls=f"fs-4 {text_cls}"),
                cls=f"rounded-3 d-flex align-items-center justify-content-center {bg_cls}",
                style="width: 48px; height: 48px;",
            ),
            Div(
                H3(value, cls="mb-0 fw-bold"),
                P(title, cls="text-muted small mb-0"),
                cls="ms-3",
            ),
            cls="d-flex align-items-center h-100",
        ),
        cls="mb-4 white-color h-100",
    )


def StatusBadgeGroup(verified: int, pending: int, flagged: int = 0) -> FT:
    """Group of badges showing log status counts."""
    badges = []
    if verified > 0:
        badges.append(Badge(str(verified), variant="success", cls="bg-success-subtle text-success border border-success-subtle me-1"))
    if pending > 0:
        badges.append(Badge(str(pending), variant="warning", cls="bg-warning-subtle text-warning border border-warning-subtle me-1"))
    if flagged > 0:
        badges.append(Badge(str(flagged), variant="danger", cls="bg-danger-subtle text-danger border border-danger-subtle"))
    if not badges:
        badges.append(Badge("0", variant="light", cls="bg-light text-muted border"))
    return Div(*badges, cls="d-flex")


def StudentActivityRow(student: dict) -> FT:
    """Row for student activity table."""
    return TRow(
        TCell(
            Div(
                Div(
                    student.get("initials", "--"),
                    cls="rounded-circle bg-primary-subtle text-primary d-flex align-items-center justify-content-center fw-bold me-3",
                    style="width: 40px; height: 40px;",
                ),
                Div(
                    Div(student.get("name", "Unknown Student"), cls="fw-bold"),
                    Div(student.get("matric", "--"), cls="text-muted small"),
                    cls="d-flex flex-column",
                ),
                cls="d-flex align-items-center",
            ),
            cls="bg-white",
        ),
        TCell(student.get("last_log", "No log yet"), cls="align-middle bg-white"),
        TCell(student.get("week", "-"), cls="align-middle bg-white"),
        TCell(
            StatusBadgeGroup(student.get("verified", 0), student.get("pending", 0), student.get("flagged", 0)),
            cls="align-middle bg-white",
        ),
        TCell(
            Div(
                A(
                    Icon("eye"),
                    href=f"/supervisor/logs?student_id={student.get('id', '')}",
                    cls="btn btn-link text-muted p-0 me-3",
                    title="View Logs",
                ),
                A(
                    Icon("chat"),
                    href=f"/supervisor/communication?tab=chat&student_id={student.get('id', '')}",
                    cls="btn btn-link text-muted p-0 me-3",
                    title="Message",
                ),
                A(
                    Icon("telephone"),
                    href=f"/supervisor/communication?tab=calls&student_id={student.get('id', '')}",
                    cls="btn btn-link text-muted p-0",
                    title="Call",
                ),
                cls="d-flex align-items-center",
            ),
            cls="align-middle bg-white",
        ),
        cls="bg-white",
    )


def StudentActivityTable(students: list[dict]) -> FT:
    """Table of assigned students and their activity."""
    return Card(
        Div(
            H5("Student Activity", cls="mb-0"),
            A("View All Logs", href="/supervisor/logs", cls="btn btn-light btn-sm border"),
            cls="d-flex justify-content-between align-items-center mb-4",
        ),
        Div(
            Table(
                THead(
                    TRow(
                        TCell("Student", cls="text-muted small border-0 bg-white"),
                        TCell("Last Log", cls="text-muted small border-0 bg-white", style="min-width: 120px;"),
                        TCell("Week", cls="text-muted small border-0 bg-white", style="min-width: 120px;"),
                        TCell("Status", cls="text-muted small border-0 bg-white"),
                        TCell("Actions", cls="text-muted small border-0 text-end pe-4 bg-white"),
                    )
                ),
                TBody(
                    *[StudentActivityRow(s) for s in students],
                ),
                cls="table-hover align-middle bg-white",
            ),
            cls="table-responsive",
        ),
        cls="bg-white",
    )


def SupervisorDashboard(
    students_assigned: int,
    pending_review: int,
    this_week_value: str,
    geofence_issues: int,
    stale_students_count: int,
    students: list[dict],
) -> FT:
    """Main supervisor dashboard page."""
    return Div(
        Div(
            H2("Supervisor Dashboard", cls="mb-0"),
            P("Overview of all assigned students", cls="text-muted"),
            cls="mb-4",
        ),
        Alert(
            Div(
                Icon("exclamation-triangle", cls="me-2"),
                f"{stale_students_count} student(s) have not logged in the past 3 days",
                cls="d-flex align-items-center",
            ),
            A("View", href="/supervisor/logs?filter=pending", cls="btn btn-outline-warning btn-sm bg-white"),
            variant="warning",
            cls="d-flex justify-content-between align-items-center mb-4 bg-warning-subtle text-warning-emphasis border border-warning-subtle",
        )
        if stale_students_count > 0
        else "",
        Row(
            Col(SupervisorStatsCard("Students Assigned", str(students_assigned), "people", "purple"), cls="mb-4"),
            Col(SupervisorStatsCard("Pending Review", str(pending_review), "clipboard-check", "orange"), cls="mb-4"),
            Col(SupervisorStatsCard("This Week", this_week_value, "calendar-check", "green"), cls="mb-4"),
            Col(SupervisorStatsCard("Geofence Issues", str(geofence_issues), "geo-alt-fill", "red"), cls="mb-4"),
            cols=1,
            cols_md=2,
            cols_lg=4,
        ),
        StudentActivityTable(students),
        cls="supervisor-dashboard pb-4",
    )
