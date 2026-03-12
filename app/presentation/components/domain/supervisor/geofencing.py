"""Supervisor geofencing map components."""

import json

from fasthtml.common import *
from faststrap import Card, Button, Icon, Row, Col, Badge, Select


def _parse_coords(value: str | None) -> tuple[float, float] | None:
    """Parse coordinate text 'lat, lng' to floats."""
    if not value:
        return None
    try:
        left, right = value.split(",", 1)
        return float(left.strip()), float(right.strip())
    except Exception:
        return None


def MapSimulation(placements: list[dict]) -> FT:
    """Leaflet map rendered from placement data (HTMX-friendly)."""
    active_count = sum(1 for p in placements if p.get("status_key") == "active")
    inactive_count = max(0, len(placements) - active_count)
    sites = []
    for p in placements:
        parsed = _parse_coords(p.get("coords"))
        if not parsed:
            continue
        lat, lng = parsed
        radius_text = str(p.get("radius_text", ""))
        radius_digits = "".join(ch for ch in radius_text if ch.isdigit())
        radius = int(radius_digits) if radius_digits else 300
        sites.append(
            {
                "company": p.get("company", "Unknown"),
                "status_key": p.get("status_key", "inactive"),
                "students_count": int(p.get("students_count", 0)),
                "address": p.get("address", ""),
                "last_checkin": p.get("last_checkin", "No check-in yet"),
                "latitude": lat,
                "longitude": lng,
                "radius": radius,
            }
        )
    sites_json = json.dumps(sites)

    script_body = f"""
    (function () {{
        const sites = {sites_json};
        const mapEl = document.getElementById('geofencing-live-map');
        if (!mapEl || !window.L) return;

        if (!sites.length) {{
            mapEl.innerHTML = '<div class="d-flex h-100 align-items-center justify-content-center text-muted small">No mapped coordinates for selected filters.</div>';
            return;
        }}

        if (mapEl._leaflet_map_ref) {{
            try {{ mapEl._leaflet_map_ref.remove(); }} catch (_) {{}}
        }}

        const map = L.map(mapEl);
        mapEl._leaflet_map_ref = map;

        L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
            maxZoom: 19,
            attribution: '&copy; OpenStreetMap'
        }}).addTo(map);

        const bounds = [];
        sites.forEach((site) => {{
            const latlng = [site.latitude, site.longitude];
            bounds.push(latlng);
            const color = site.status_key === 'active' ? '#198754' : '#6c757d';

            const marker = L.circleMarker(latlng, {{
                radius: 8,
                color: color,
                fillColor: color,
                fillOpacity: 0.9,
                weight: 2
            }}).addTo(map);

            L.circle(latlng, {{
                radius: site.radius || 300,
                color: color,
                fillColor: color,
                fillOpacity: 0.10,
                weight: 1.5
            }}).addTo(map);

            marker.bindPopup(
                `<div style="min-width:220px">
                    <div style="font-weight:700;">${{site.company}}</div>
                    <div style="font-size:12px;color:#6b7280;margin-top:4px;">${{site.address || ''}}</div>
                    <div style="font-size:12px;margin-top:6px;">Students: ${{site.students_count}}</div>
                    <div style="font-size:12px;">Last check-in: ${{site.last_checkin}}</div>
                </div>`
            );
        }});

        if (bounds.length === 1) map.setView(bounds[0], 15);
        else map.fitBounds(bounds, {{ padding: [24, 24] }});
    }})();
    """

    legend = Div(
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
    )

    map_shell = Div(
        legend,
        Div(id="geofencing-live-map", style="height: 380px; width: 100%;"),
        cls="position-relative rounded-3 mb-4 overflow-hidden border",
    )

    return Div(
        Link(rel="stylesheet", href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"),
        Script(src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"),
        map_shell,
        Script(script_body),
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
                            *[
                                (value, label, value == selected_company)
                                for value, label in company_options
                            ],
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
                            ("all", "All Statuses", selected_status == "all"),
                            ("active", "Active", selected_status == "active"),
                            ("inactive", "Inactive", selected_status == "inactive"),
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
