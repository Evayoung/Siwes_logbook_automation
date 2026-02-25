"""Supervisor geofencing map components."""

from fasthtml.common import *
from faststrap import Card, Button, Icon, Row, Col, Badge, Select


def _zone_position(index: int) -> dict:
    """Return stable map positions for placement zones."""
    positions = [
        {"top": 18, "left": 16},
        {"top": 22, "left": 56},
        {"top": 44, "left": 28},
        {"top": 52, "left": 66},
        {"top": 30, "left": 78},
        {"top": 66, "left": 14},
    ]
    return positions[index % len(positions)]


def MapZone(site: dict, index: int) -> FT:
    """Placement bubble on the map."""
    is_active = site.get("status_key") == "active"
    bg_color = "bg-success" if is_active else "bg-secondary"
    position = _zone_position(index)
    label = f"{site.get('students_count', 0)} student"
    if site.get("students_count", 0) != 1:
        label += "s"

    return Div(
        Div(
            Div(label, cls="small fw-bold text-white text-center px-2"),
            cls=f"rounded-circle {bg_color} d-flex align-items-center justify-content-center shadow",
            style="width: 96px; height: 96px;",
        ),
        Div(site.get("company", "Unknown"), cls="small text-muted text-center mt-1"),
        cls="position-absolute",
        style=f"top: {position['top']}%; left: {position['left']}%; transform: translate(-50%, -50%);",
    )


def MapSimulation(placements: list[dict]) -> FT:
    """Visual geofencing map from placement data."""
    active_count = sum(1 for p in placements if p.get("status_key") == "active")
    inactive_count = max(0, len(placements) - active_count)

    return Div(
        Div(
            Div(
                Div(cls="bg-success rounded-circle me-2", style="width: 12px; height: 12px;"),
                f"Active ({active_count})",
                cls="d-flex align-items-center me-3",
            ),
            Div(
                Div(cls="bg-secondary rounded-circle me-2", style="width: 12px; height: 12px;"),
                f"Inactive ({inactive_count})",
                cls="d-flex align-items-center",
            ),
            cls="position-absolute top-0 end-0 m-3 bg-white p-3 rounded shadow-sm d-flex",
            style="z-index: 10;",
        ),
        *[MapZone(site, idx) for idx, site in enumerate(placements)],
        cls="position-relative bg-light rounded-3 mb-4",
        style="""
            min-height: 380px;
            background-image:
                linear-gradient(rgba(200, 200, 200, 0.2) 1px, transparent 1px),
                linear-gradient(90deg, rgba(200, 200, 200, 0.2) 1px, transparent 1px);
            background-size: 50px 50px;
        """,
    )


def PlacementFilter(
    companies: list[str],
    selected_company: str = "all",
    selected_status: str = "all",
    oob: bool = False,
) -> FT:
    """Filter controls for placement sites using HTMX."""
    company_options = [("all", "All Companies")] + [(name, name) for name in companies]

    return Card(
        Form(
            Div(
                Icon("funnel", cls="me-2"),
                "Filters",
                cls="fw-bold mb-3 d-flex align-items-center",
            ),
            Row(
                Col(
                    Div(
                        Label("Filter by Company", cls="form-label small text-muted"),
                        Select(
                            "company",
                            options=company_options,
                            selected=selected_company,
                            cls="form-select",
                        ),
                    ),
                    xs=12,
                    md=6,
                    cls="mb-3 mb-md-0",
                ),
                Col(
                    Div(
                        Label("Filter by Status", cls="form-label small text-muted"),
                        Select(
                            "status",
                            options=[
                                ("all", "All Statuses"),
                                ("active", "Active"),
                                ("inactive", "Inactive"),
                            ],
                            selected=selected_status,
                            cls="form-select",
                        ),
                    ),
                    xs=12,
                    md=6,
                ),
            ),
            Div(
                A(
                    "Reset",
                    href="/supervisor/geofencing",
                    cls="btn btn-light border",
                    hx_get="/supervisor/geofencing",
                    hx_target="#geofencing-content",
                    hx_swap="outerHTML",
                    hx_push_url="true",
                ),
                cls="mt-3 d-flex justify-content-end",
            ),
            hx_get="/supervisor/geofencing",
            hx_trigger="change, submit",
            hx_target="#geofencing-content",
            hx_swap="outerHTML",
            hx_push_url="true",
        ),
        cls="mb-4 bg-white",
        id="geofencing-filter",
        hx_swap_oob="true" if oob else None,
    )


def PlacementSiteCard(site: dict) -> FT:
    """Card showing placement site details."""
    is_active = site.get("status_key") == "active"
    status = "Active" if is_active else "Inactive"
    status_color = "success" if is_active else "secondary"
    students = site.get("students") or []

    return Card(
        Div(
            Div(
                Icon("geo-alt-fill", cls="me-2 text-primary"),
                H6(site.get("company", "Unknown Placement"), cls="mb-0 fw-bold"),
                cls="d-flex align-items-center mb-2",
            ),
            P(site.get("coords", "Coordinates not set"), cls="text-muted small mb-2"),
            P(site.get("address", ""), cls="text-muted small mb-3"),
            Div(
                Badge(
                    status,
                    variant=status_color,
                    cls=f"bg-{status_color}-subtle text-{status_color} border border-{status_color}-subtle w-100 py-2",
                ),
                cls="mb-3",
            ),
            Div(
                P(f"Students ({len(students)})", cls="small text-muted mb-2"),
                *[Div(f"- {name}", cls="small mb-1") for name in students[:6]],
                Div(f"+ {len(students) - 6} more", cls="small text-muted") if len(students) > 6 else "",
                cls="mb-3",
            ),
            Div(
                P(f"Last check-in: {site.get('last_checkin', 'No check-in yet')}", cls="small text-muted mb-1"),
                P(site.get("radius_text", ""), cls="small text-success mb-0"),
                cls="pt-2 border-top",
            ),
        ),
        cls="h-100 bg-white",
    )


def InactiveSitesAlert(inactive_count: int) -> FT:
    """Alert for inactive placement sites."""
    if inactive_count <= 0:
        return ""
    return Card(
        Div(
            Icon("exclamation-triangle", cls="me-2 text-warning"),
            "Inactive Sites",
            cls="fw-bold mb-2 d-flex align-items-center",
        ),
        P(
            f"{inactive_count} placement site(s) have no recent activity. Follow up with the assigned students.",
            cls="text-muted small mb-0",
        ),
        cls="bg-warning-subtle border border-warning-subtle",
    )


def GeofencingContent(placements: list[dict]) -> FT:
    """Swap target for map and placement cards."""
    inactive_count = sum(1 for p in placements if p.get("status_key") == "inactive")

    return Div(
        MapSimulation(placements),
        H5("Placement Sites", cls="mb-3"),
        Row(
            *[
                Col(PlacementSiteCard(site), xs=12, md=6, lg=4, cls="mb-4")
                for site in placements
            ],
            cols=1, cols_md=2, cols_lg=4
        )
        if placements
        else Div(
            Card(
                Div(
                    Icon("geo-alt", cls="me-2 text-muted"),
                    "No placement data matches this filter.",
                    cls="d-flex align-items-center text-muted",
                ),
                cls="bg-white",
            )
        ),
        InactiveSitesAlert(inactive_count),
        id="geofencing-content",
    )


def GeofencingPage(
    placements: list[dict],
    companies: list[str],
    selected_company: str = "all",
    selected_status: str = "all",
) -> FT:
    """Main geofencing map page."""
    return Div(
        Div(
            H2("Geofencing Map", cls="mb-0"),
            P("Location validation view for all assigned placement sites", cls="text-muted"),
            cls="mb-4",
        ),
        PlacementFilter(companies, selected_company=selected_company, selected_status=selected_status),
        GeofencingContent(placements),
        cls="geofencing-page pb-4",
    )
