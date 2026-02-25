"""Navigation components for student and supervisor interfaces."""

from fasthtml.common import *
from faststrap import Icon


def LogoutConfirmModal() -> FT:
    """Shared logout confirmation modal."""
    return Div(
        Div(
            Div(
                Div(
                    H5("Confirm Logout", cls="modal-title"),
                    Button(type="button", cls="btn-close", data_bs_dismiss="modal", aria_label="Close"),
                    cls="modal-header",
                ),
                Div(
                    P("Are you sure you want to log out?", cls="mb-0"),
                    cls="modal-body",
                ),
                Div(
                    Button("Cancel", type="button", cls="btn btn-outline-secondary", data_bs_dismiss="modal"),
                    Form(
                        Button(
                            Span(Span(cls="spinner-border spinner-border-sm me-2 d-none", id="logout-confirm-spinner"), "Logout"),
                            type="submit",
                            cls="btn btn-danger",
                            id="logout-confirm-submit",
                        ),
                        action="/logout",
                        method="post",
                        cls="d-inline",
                        id="logout-confirm-form",
                    ),
                    cls="modal-footer",
                ),
                cls="modal-content",
            ),
            cls="modal-dialog modal-dialog-centered",
        ),
        cls="modal fade",
        id="logout-confirm-modal",
        tabindex="-1",
        aria_hidden="true",
    )


def StudentSidebarNav(active_page: str = "dashboard") -> FT:
    """Student sidebar navigation - responsive for all screen sizes.
    
    Uses Bootstrap offcanvas for mobile, fixed sidebar for desktop.
    
    Args:
        active_page: Current active page
    
    Returns:
        Unified sidebar for all screen sizes
    """
    nav_items = [
        {"icon": "grid-fill", "label": "Dashboard", "href": "/student/dashboard", "key": "dashboard"},
        {"icon": "journal-text", "label": "Daily Logbook", "href": "/student/logbook", "key": "logbook"},
        {"icon": "chat-dots-fill", "label": "Chat & Calls", "href": "/student/communication", "key": "communication"},
        {"icon": "person-fill", "label": "Profile", "href": "/student/profile", "key": "profile"},
    ]
    
    return Div(
        # Header
        # Div(
        #     Icon("mortarboard-fill", cls="me-2"),
        #     "SIWES Portal",

        #     cls="sidebar-header"
        # ),
        Div(
            Div(
                Icon("mortarboard-fill", style="font-size: 1.75rem;"), 
                cls="text-center text-white d-flex justify-content-center align-items-center",
                style="background-color: var(--bs-primary); border-radius: 10px; width: 50px; height: 50px;"
            ),
            Div(
                P("SIWES Portal", cls="m-0 fw-bold text-white"),
                P("Student", cls="mb-0 text-white-50", style="font-size: 0.875rem;"),
                cls="d-flex flex-column justify-content-center align-items-start",
            ),
            cls="sidebar-header d-flex align-items-center gap-4 px-3 py-2 mb-5",
        ),

        # Navigation items
        Div(
            *[
                A(
                    Icon(item["icon"], cls="nav-item-icon"),
                    item["label"],
                    href=item["href"],
                    cls=f"nav-item {'active' if active_page == item['key'] else ''}"
                )
                for item in nav_items
            ],
            cls="nav-items flex-grow-1"
        ),
        
        # Logout at bottom
        Div(
            A(
                Icon("box-arrow-right", cls="nav-item-icon"),
                "Logout",
                href="#",
                cls="nav-item",
                role="button",
                data_bs_toggle="modal",
                data_bs_target="#logout-confirm-modal",
            ),
            cls="mt-auto"
        ),
        
        # Bootstrap classes for responsive behavior:
        # - d-flex flex-column: Layout
        # - offcanvas offcanvas-start: Mobile slide-in from left
        # - d-lg-block: Always visible on desktop (≥992px)
        # - position-lg-fixed: Fixed position on desktop
        cls="sidebar d-flex flex-column offcanvas offcanvas-start d-lg-block position-lg-fixed",
        style="width: 280px; min-height: 95vh; z-index: 1040;",
        id="sidebar",
        tabindex="-1"
    )


def StudentBottomNav(active_page: str = "dashboard") -> FT:
    """Student bottom navigation (mobile only).
    
    Args:
        active_page: Current active page
    
    Returns:
        Bottom navigation HTML
    """
    nav_items = [
        {"icon": "grid-fill", "label": "Dashboard", "href": "/student/dashboard", "key": "dashboard"},
        {"icon": "journal-text", "label": "Logbook", "href": "/student/logbook", "key": "logbook"},
        {"icon": "chat-dots-fill", "label": "Chat & Calls", "href": "/student/communication", "key": "communication"},
        {"icon": "person-fill", "label": "Profile", "href": "/student/profile", "key": "profile"},
    ]
    
    return Div(
        Div(
            *[
                A(
                    Icon(item["icon"], cls="mobile-nav-icon"),
                    Span(item["label"], cls="mobile-nav-label"),
                    href=item["href"],
                    cls=f"mobile-nav-item {'active' if active_page == item['key'] else ''}"
                )
                for item in nav_items
            ],
            # Menu button - toggles offcanvas sidebar
            A(
                Icon("list", cls="mobile-nav-icon"),
                Span("Menu", cls="mobile-nav-label"),
                cls="mobile-nav-item",
                **{"data-bs-toggle": "offcanvas", "data-bs-target": "#sidebar"},
                role="button"
            ),
            cls="d-flex justify-content-around align-items-center w-100"
        ),
        cls="mobile-nav"
    )


def SupervisorSidebarNav(active_page: str = "dashboard") -> FT:
    """Supervisor sidebar navigation - responsive for all screen sizes.
    
    Args:
        active_page: Current active page
    
    Returns:
        Unified sidebar for all screen sizes
    """
    nav_items = [
        {"icon": "grid-fill", "label": "Dashboard", "href": "/supervisor/dashboard", "key": "dashboard"},
        {"icon": "journal-text", "label": "Student Logs", "href": "/supervisor/logs", "key": "logs"},
        {"icon": "geo-alt-fill", "label": "Geofencing Map", "href": "/supervisor/geofencing", "key": "geofencing"},
        {"icon": "chat-dots-fill", "label": "Chat & Calls", "href": "/supervisor/communication", "key": "communication"},
    ]
    
    return Div(
        # Header
        # Div(
        #     Icon("mortarboard-fill", cls="me-2"),
        #     "SIWES Portal",
        #     cls="sidebar-header"
        # ),
        
        Div(
            Div(
                Icon("mortarboard-fill", style="font-size: 1.75rem;"), 
                cls="text-center text-white d-flex justify-content-center align-items-center",
                style="background-color: var(--bs-primary); border-radius: 10px; width: 50px; height: 50px;"
            ),
            Div(
                P("SIWES Portal", cls="m-0 fw-bold text-white"),
                P("Supervisor", cls="mb-0 text-white-50", style="font-size: 0.875rem;"),
                cls="d-flex flex-column justify-content-center align-items-start",
            ),
            cls="sidebar-header d-flex align-items-center gap-4 px-3 py-2 mb-5",
        ),

        # Navigation items
        Div(
            *[
                A(
                    Icon(item["icon"], cls="nav-item-icon"),
                    item["label"],
                    href=item["href"],
                    cls=f"nav-item {'active' if active_page == item['key'] else ''}"
                )
                for item in nav_items
            ],
            cls="nav-items flex-grow-1"
        ),
        
        # Logout at bottom
        Div(
            A(
                Icon("box-arrow-right", cls="nav-item-icon"),
                "Logout",
                href="#",
                cls="nav-item",
                role="button",
                data_bs_toggle="modal",
                data_bs_target="#logout-confirm-modal",
            ),
            cls="mt-auto"
        ),
        
        cls="sidebar d-flex flex-column offcanvas offcanvas-start d-lg-block position-lg-fixed",
        style="width: 280px; min-height: 95vh; z-index: 1040;",
        id="sidebar",
        tabindex="-1"
    )


def SupervisorBottomNav(active_page: str = "dashboard") -> FT:
    """Bottom navigation for supervisor on mobile devices.
    
    Args:
        active_page: Current active page key
    
    Returns:
        Bottom navigation HTML
    """
    nav_items = [
        {"icon": "grid-fill", "label": "Dashboard", "href": "/supervisor/dashboard", "key": "dashboard"},
        {"icon": "journal-text", "label": "Logs", "href": "/supervisor/logs", "key": "logs"},
        {"icon": "geo-alt-fill", "label": "Map", "href": "/supervisor/geofencing", "key": "geofencing"},
        {"icon": "chat-dots-fill", "label": "Chat", "href": "/supervisor/communication", "key": "communication"},
    ]
    
    return Div(
        # Bottom nav
        Div(
            *[
                A(
                    Icon(item["icon"], cls="mobile-nav-icon"),
                    Span(item["label"], cls="mobile-nav-label"),
                    href=item["href"],
                    cls=f"mobile-nav-item {'active' if active_page == item['key'] else ''}"
                )
                for item in nav_items
            ],
            # Menu toggle button (Bootstrap offcanvas)
            A(
                Icon("list", cls="mobile-nav-icon"),
                Span("Menu", cls="mobile-nav-label"),
                cls="mobile-nav-item",
                data_bs_toggle="offcanvas",
                data_bs_target="#sidebar",
                role="button"
            ),
            cls="mobile-nav",
            id="mobile-nav"
        )
    )
