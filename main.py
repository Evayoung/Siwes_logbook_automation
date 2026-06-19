"""Main application entry point for the SIWES Logbook System.

This module initializes the FastHTML application, sets up routes,
and configures the server.
"""

import sys

from fasthtml.common import *
from starlette.middleware import Middleware
from starlette.responses import RedirectResponse
from app.infrastructure.cache_middleware import NoStoreMiddleware
from app.infrastructure.database.middleware import DBSessionMiddleware
from faststrap import add_bootstrap, mount_assets
from faststrap.pwa import add_pwa
from app.config import get_settings
from app.infrastructure.database import init_db
from app.infrastructure.usability_data_patch import apply_usability_data_patch
from app.presentation.routes.auth import setup_auth_routes
from app.presentation.components.shared import SIWES_THEME, setup_siwes_defaults


# Get settings
settings = get_settings()

# Create FastHTML app with session support and DB middleware
app = FastHTML(
    secret_key=settings.secret_key,
    session_cookie="siwes_session",
    middleware=[
        Middleware(NoStoreMiddleware),
        Middleware(DBSessionMiddleware),
    ]
)

# Apply Faststrap theme
add_bootstrap(app, theme=SIWES_THEME, mode="light")

# Add PWA capabilities (following pwa_demo.py pattern)
add_pwa(
    app,
    name="SIWES Logbook",
    short_name="SIWES",
    description="Student Industrial Work Experience Scheme - Digital Logbook for tracking internship activities",
    theme_color="#6366f1",  # Primary purple from SIWES_THEME
    background_color="#ffffff",
    icon_path="/assets/icon.png",
    display="standalone",
    start_url="/",
    scope="/",
    service_worker=True,
    offline_page=True,
)

# Add custom headers after Faststrap and PWA
app.hdrs = app.hdrs + [
    Link(rel="stylesheet", href="/assets/custom.css"),
    Script(src="https://unpkg.com/htmx.org@1.9.10"),
    Script(f"window.__siwesOfflineLoginDays={int(settings.offline_login_grace_days)};"),
    Script(src="/assets/pwa_install_prompt.js"),
    Script(src="/assets/offline_resume.js?v=20260226-1"),
]

# Setup component defaults
setup_siwes_defaults()

# Mount static files for custom CSS and icon
mount_assets(app, "app/presentation/assets", url_path="/assets")


# Initialize database in development or when explicitly enabled.
# Production deployments should run scripts/migrate_to_supabase.py instead.
if settings.environment != "production" or settings.auto_init_db:
    init_db()

# Keep deployed usability-test accounts aligned with the approved client data.
# This is idempotent and does not reset logs, chats, calls, or notifications.
try:
    apply_usability_data_patch()
except Exception as exc:
    print(f"[DATA PATCH] skipped usability data patch: {exc}")

# Setup routes
setup_auth_routes(app)
from app.presentation.routes.notifications import register_notification_routes
register_notification_routes(app)
from app.presentation.routes.calls import register_call_routes
register_call_routes(app)
from app.presentation.routes.chat import register_chat_routes
register_chat_routes(app)
from app.presentation.routes.student import setup_student_routes
setup_student_routes(app)
from app.presentation.routes.supervisor import setup_supervisor_routes
setup_supervisor_routes(app)


# Health check endpoint
@app.get("/health")
def health_check():
    """Health check endpoint for monitoring."""
    return {"status": "healthy", "service": "siwes-logbook"}


@app.get("/favicon.ico")
def favicon():
    """Serve favicon via existing app icon."""
    return RedirectResponse(url="/assets/icon.png", status_code=307)


@app.get("/.well-known/assetlinks.json")
def assetlinks():
    """Return empty digital asset links file for Android verifier probes."""
    return JSONResponse([])


# Run the application
if __name__ == "__main__":
    serve(port=5031)

