"""Layout components for SIWES application.

Provides layout wrappers following FastHTML patterns.
"""

from fasthtml.common import *
from faststrap import Container, Card, Icon, Button
from typing import Any


def _user_initials(full_name: str) -> str:
    parts = [p for p in (full_name or "").split() if p]
    if not parts:
        return "--"
    return "".join(p[0] for p in parts[:2]).upper()


def _user_surname(full_name: str) -> str:
    parts = [p for p in (full_name or "").split() if p]
    if not parts:
        return "User"
    return parts[-1]


def DashboardTopBar(user_name: str = "User") -> FT:
    """Fixed glass top bar with connectivity, notifications, and user identity."""
    initials = _user_initials(user_name)
    surname = _user_surname(user_name)

    return Div(
        Div(
            Div(
                Icon("wifi", cls="me-2"),
                Span("Online", id="topbar-network-text"),
                cls="topbar-network-badge",
                id="topbar-network-badge",
            ),
            Div(
                Div(
                    Button(
                        Icon("bell", cls="fs-5"),
                        Span("0", id="topbar-notification-count", cls="topbar-notification-count d-none"),
                        type="button",
                        variant="light",
                        cls="topbar-icon-btn border",
                        id="topbar-notification-toggle",
                    ),
                    Div(
                        Div(
                            H6("Notifications", cls="mb-0 fw-bold"),
                            Button(
                                "Mark all read",
                                type="button",
                                variant="link",
                                cls="p-0 small text-decoration-none",
                                id="topbar-mark-all-read",
                            ),
                            cls="d-flex justify-content-between align-items-center mb-2",
                        ),
                        Div(
                            Div("No notifications yet.", cls="text-muted small p-2"),
                            id="topbar-notification-list",
                        ),
                        cls="topbar-notification-menu d-none",
                        id="topbar-notification-menu",
                    ),
                    cls="position-relative me-3",
                ),
                Div(
                    Div(initials, cls="topbar-user-avatar"),
                    Span(surname, cls="fw-semibold"),
                    cls="d-flex align-items-center gap-2",
                ),
                cls="d-flex align-items-center gap-2"
            ),
            cls="d-flex align-items-center justify-content-between px-3 w-100",
        ),
        cls="dashboard-topbar",
    )



def AuthLayout(*content: Any, **kwargs: Any) -> FT:
    """Authentication layout for login/register pages.
    
    Args:
        *content: Content elements to display
        **kwargs: Additional attributes
    
    Returns:
        Div with auth layout styling
    """
    return Div(
        Container(
            Card(
                *content,
                cls="shadow-lg p-4",
                style="min-width: 320px;"
            ),
            cls="d-flex align-items-center justify-content-center min-vh-100",
            style="max-width: 500px; width: 100%; padding: 1rem;"
        ),
        style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); min-height: 100vh;",
        **kwargs
    )


def DashboardLayout(
    *content: Any,
    sidebar: FT | None = None,
    bottom_nav: FT | None = None,
    current_user: Any | None = None,
    **kwargs: Any
) -> FT:
    """Dashboard layout with responsive sidebar and bottom nav.
    
    Args:
        *content: Main content elements
        sidebar: Responsive sidebar (offcanvas on mobile, fixed on desktop)
        bottom_nav: Bottom navigation for mobile
        **kwargs: Additional attributes
    
    Returns:
        Div with responsive dashboard layout
    """
    from app.presentation.components.ui.call_notification import CallNotificationModal
    from app.presentation.components.ui.navigation import LogoutConfirmModal
    
    elements = []
    
    # Call Notification Modal (hidden by default, shown via SSE)
    elements.append(CallNotificationModal())
    elements.append(LogoutConfirmModal())
    
    # Unified sidebar (responsive for all screen sizes)
    if sidebar:
        elements.append(sidebar)
    
    if isinstance(current_user, str):
        user_name = current_user
        role_value = ""
        user_email = ""
    else:
        user_name = getattr(current_user, "full_name", "User")
        role = getattr(current_user, "role", None)
        role_value = getattr(role, "value", str(role or "")).lower()
        user_email = getattr(current_user, "email", "")
    elements.append(DashboardTopBar(user_name=user_name))
    elements.append(
        Div(
            id="offline-auth-state",
            data_role=role_value,
            data_name=user_name,
            data_email=user_email,
            cls="d-none",
        )
    )

    # Main content
    elements.append(
        Container(
            *content,
            fluid=True,
            cls="main-content"
        )
    )
    
    # Bottom nav (mobile only)
    if bottom_nav:
        elements.append(bottom_nav)
    
    # SSE Notification Listener Script
    elements.append(Script(src="/assets/call_notifications.js?v=20260612-1"))
    
    return Div(*elements, **kwargs)
