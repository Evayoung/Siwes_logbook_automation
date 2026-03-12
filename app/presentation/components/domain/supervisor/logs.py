"""Supervisor student logs review components."""

from fasthtml.common import *
from faststrap import Card, Button, Icon, Row, Col, Badge, Select, ToggleGroup


def LogFilterTabs(active_filter: str = "all", oob: bool = False, student_id: str | None = None) -> FT:
    """Filter tabs for log review."""
    filters = [
        {"key": "all", "label": "All Logs"},
        {"key": "pending", "label": "Pending"},
        {"key": "verified", "label": "Verified"},
        {"key": "flagged", "label": "Flagged"},
    ]

    student_q = f"?student_id={student_id}" if student_id else ""
    tabs = ToggleGroup(
        *[
            Button(
                f["label"],
                variant="light",
                cls="comm-view-btn",
                hx_get=f"/supervisor/logs/filter/{f['key']}{student_q}",
                hx_target="#logs-container",
                hx_swap="innerHTML",
                style="max-width: 100px;"
            )
            for f in filters
        ],
        active_index=next((idx for idx, f in enumerate(filters) if f["key"] == active_filter), 0),
        cls="comm-view-toggle d-flex flex-wrap gap-3 mb-4 justify-content-start",
    )
    return Div(
        tabs,
        id="log-filter-tabs",
        hx_swap_oob="true" if oob else None,
    )


def LogCard(log: dict, show_checkbox: bool = True) -> FT:
    """Individual log entry card."""
    status_styles = {
        "Pending": {"icon": "clock", "color": "warning", "bg": "bg-warning-subtle", "text": "text-warning"},
        "Verified": {"icon": "check-circle", "color": "success", "bg": "bg-success-subtle", "text": "text-success"},
        "Flagged": {"icon": "x-circle", "color": "danger", "bg": "bg-danger-subtle", "text": "text-danger"},
    }
    style = status_styles.get(log["status"], status_styles["Pending"])

    geofence_ok = log.get("geofence_status") == "within"
    geofence_color = "success" if geofence_ok else "danger"
    geofence_text = "Within geofence" if geofence_ok else "Outside geofence"

    return Card(
        Div(
            Div(
                Icon(style["icon"], cls="me-1 small"),
                Span(log["status"], cls="small fw-medium"),
                cls=f"d-flex align-items-center position-absolute top-0 end-0 m-3 {style['text']} {style['bg']} px-2 py-1 rounded-pill border border-{style['color']}-subtle",
                style="font-size: 0.75rem;",
            ),
            Div(
                Input(
                    type="checkbox",
                    name="selected_logs",
                    value=log["id"],
                    cls="form-check-input me-3 log-checkbox",
                    style="width: 20px; height: 20px; margin-top: 0.25rem;",
                )
                if show_checkbox
                else "",
                Div(
                    H6(log["student_name"], cls="mb-1 fw-bold"),
                    P(
                        f"{log['matric']} - Week {log['week']} - {log['date']}",
                        cls="text-muted small mb-2",
                    ),
                    P(log["description"], cls="mb-2 text-dark"),
                    Div(
                        Icon("geo-alt-fill", cls=f"me-1 text-{geofence_color}"),
                        geofence_text,
                        cls=f"small text-{geofence_color} mb-0 d-flex align-items-center",
                    ),
                    cls="flex-grow-1 pe-5",
                ),
                cls="d-flex align-items-start",
            ),
            Div(
                Button(
                    Icon("file-text", cls="me-2"),
                    "Review",
                    variant="primary",
                    size="sm",
                    hx_get=f"/supervisor/logs/review/{log['id']}",
                    hx_target="body",
                    hx_swap="innerHTML",
                ),
                cls="d-flex justify-content-end mt-3 border-top pt-3",
            ),
        ),
        cls="mb-3 bg-white position-relative",
    )


def StudentLogsPage(logs: list | None = None, active_filter: str = "all", student_id: str | None = None) -> FT:
    """Main student logs review page."""
    logs = logs or []

    return Form(
        Div(
            Div(
                H2("Student Logs", cls="mb-0"),
                P("Review and verify student log entries", cls="text-muted"),
            ),
            Button(
                Icon("check-circle", cls="me-2"),
                "Verify Selected",
                variant="success",
                cls="bg-success text-white align-self-start verify-selected-btn",
                id="verify-selected-btn",
                type="submit",
            ),
            cls="d-flex justify-content-between align-items-center mb-4",
        ),
        LogFilterTabs(active_filter=active_filter, student_id=student_id),
        Div(id="logs-feedback"),
        Div(*[LogCard(log) for log in logs], id="logs-container"),
        cls="student-logs-page",
        hx_post="/supervisor/logs/verify-selected",
        hx_target="#logs-feedback",
        hx_swap="innerHTML",
        id="supervisor-logs-form",
    )


def LogReviewPage(
    log_id: str,
    log_data: dict,
    review_notice: str | None = None,
    review_notice_variant: str = "success",
) -> FT:
    """Detailed log review page."""
    location_status = log_data["location"]["status"]
    status_variant = "success" if location_status.lower().startswith("within") else "danger"

    return Div(
        Button(
            Icon("arrow-left", cls="me-2"),
            variant="link",
            cls="text-dark mb-3 p-0",
            hx_get="/supervisor/logs",
            hx_target="body",
            hx_swap="innerHTML",
        ),
        Div(
            H2("Log Review", cls="mb-0"),
            P(f"Week {log_data['log']['week']} - {log_data['log']['date']}", cls="text-muted"),
            cls="mb-4",
        ),
        Card(
            H5("Student Information", cls="mb-3"),
            Row(
                Col(
                    Div(
                        P("Name", cls="text-muted small mb-1"),
                        P(log_data["student"]["name"], cls="fw-medium mb-0"),
                    ),
                    xs=12,
                    md=6,
                    cls="mb-3",
                ),
                Col(
                    Div(
                        P("Matric Number", cls="text-muted small mb-1"),
                        P(log_data["student"]["matric"], cls="fw-medium mb-0"),
                    ),
                    xs=12,
                    md=6,
                    cls="mb-3",
                ),
                Col(
                    Div(
                        P("Company", cls="text-muted small mb-1"),
                        P(log_data["student"]["company"], cls="fw-medium mb-0"),
                    ),
                    xs=12,
                    md=12,
                ),
            ),
            cls="mb-4 bg-white",
        ),
        Card(
            H5("Log Entry", cls="mb-3"),
            Div(
                P("Activity Description", cls="text-muted small mb-2"),
                P(log_data["log"]["description"], cls="mb-4"),
            ),
            Row(
                Col(
                    Div(
                        Icon("clock", cls="me-2 text-muted"),
                        "Hours Logged",
                        cls="text-muted small mb-1 d-flex align-items-center",
                    ),
                    H4(log_data["log"]["hours"], cls="mb-0 fw-bold"),
                    xs=12,
                    md=6,
                    cls="mb-3 mb-md-0",
                ),
                Col(
                    Div(
                        Icon("calendar", cls="me-2 text-muted"),
                        "Day",
                        cls="text-muted small mb-1 d-flex align-items-center",
                    ),
                    H4(log_data["log"]["day"], cls="mb-0 fw-bold"),
                    xs=12,
                    md=6,
                ),
            ),
            cls="mb-4 bg-white",
        ),
        Card(
            Div(
                Icon("geo-alt-fill", cls="me-2 text-primary"),
                "Location Information",
                cls="d-flex align-items-center mb-3",
            ),
            Div(
                Div(
                    P("Location Status", cls="text-muted small mb-2"),
                    Badge(
                        log_data["location"]["status"],
                        variant=status_variant,
                        cls=f"bg-{status_variant}-subtle text-{status_variant} border border-{status_variant}-subtle px-3 py-2",
                    ),
                ),
                cls=f"mb-3 p-3 bg-{status_variant}-subtle rounded-3",
            ),
            Row(
                Col(
                    Div(
                        P("GPS Coordinates", cls="text-muted small mb-1"),
                        P(log_data["location"]["coords"], cls="fw-medium mb-0"),
                    ),
                    xs=12,
                    md=6,
                    cls="mb-3",
                ),
                Col(
                    Div(
                        P("Distance from Workplace", cls="text-muted small mb-1"),
                        P(log_data["location"]["distance"], cls="fw-medium mb-0"),
                    ),
                    xs=12,
                    md=6,
                    cls="mb-3",
                ),
            ),
            Div(
                P("Geofence Radius", cls="text-muted small mb-2"),
                P(log_data["location"]["radius_text"], cls="text-success small mb-0"),
                cls="mb-2",
            ),
            cls="mb-4 bg-white",
        ),
        Card(
            H5("Review & Verification", cls="mb-3"),
            Div(
                review_notice,
                cls=f"alert alert-{review_notice_variant} mb-3",
                id="review-feedback",
            ) if review_notice else Div(id="review-feedback"),
            Form(
                Div(
                    Label("Status", cls="form-label small text-muted"),
                    Select(
                        "review_status",
                        ("pending", "Pending", log_data["log"]["status"] == "pending"),
                        ("verified", "Verified", log_data["log"]["status"] == "verified"),
                        ("flagged", "Flagged", log_data["log"]["status"] == "flagged"),
                        cls="form-select mb-3",
                    ),
                ),
                Div(
                    Label("Comment (Optional)", cls="form-label small text-muted"),
                    Textarea(
                        name="review_comment",
                        placeholder="Add any comments or notes about this log entry...",
                        rows=4,
                        cls="form-control mb-4",
                        value=log_data["log"].get("review_comment") or "",
                    ),
                ),
                Div(
                    Div(
                        Span("Last Reviewed:", cls="text-muted small me-2"),
                        Span(log_data["log"].get("reviewed_at") or "Not reviewed yet", cls="small fw-medium"),
                        cls="mb-1",
                    ),
                    Div(
                        Span("Reviewed By:", cls="text-muted small me-2"),
                        Span(log_data["log"].get("reviewed_by") or "-", cls="small fw-medium"),
                    ),
                    cls="mb-3",
                ),
                Div(
                    Button(
                        "Cancel",
                        variant="light",
                        cls="me-2 border",
                        type="button",
                        hx_get="/supervisor/logs",
                        hx_target="body",
                    ),
                    Button(
                        Span(
                            Span(
                                cls="spinner-border spinner-border-sm me-2 d-none",
                                id="review-save-spinner",
                                aria_hidden="true",
                            ),
                            "Save Review",
                        ),
                        variant="primary",
                        cls="bg-primary text-white px-4",
                        type="submit",
                        id="review-save-btn",
                    ),
                    cls="d-flex justify-content-end",
                ),
                hx_post=f"/supervisor/logs/review/{log_id}",
                hx_target="body",
                hx_swap="innerHTML",
                id="review-form",
            ),
            Script(
                """
                (function () {
                    const form = document.getElementById('review-form');
                    const btn = document.getElementById('review-save-btn');
                    const spinner = document.getElementById('review-save-spinner');
                    if (!form || !btn) return;

                    form.addEventListener('htmx:beforeRequest', function () {
                        btn.setAttribute('disabled', 'disabled');
                        if (spinner) spinner.classList.remove('d-none');
                    });
                    form.addEventListener('htmx:afterRequest', function () {
                        btn.removeAttribute('disabled');
                        if (spinner) spinner.classList.add('d-none');
                    });
                })();
                """
            ),
            cls="mb-4 bg-white",
        ),
        cls="log-review-page mx-auto px-3",
        style="max-width: 900px;",
    )
