"""Main application entry point for the SIWES Logbook System.

This module initializes the FastHTML application, sets up routes,
and configures the server.
"""

import sys
from pathlib import Path

from fasthtml.common import *
from starlette.middleware import Middleware
from starlette.responses import FileResponse
from app.infrastructure.database.middleware import DBSessionMiddleware
from faststrap import add_bootstrap, mount_assets
from faststrap.pwa import add_pwa
from app.config import get_settings
from app.infrastructure.database import init_db
from app.presentation.routes.auth import setup_auth_routes
from app.presentation.components.shared import SIWES_THEME, setup_siwes_defaults


# Get settings
settings = get_settings()

# Create FastHTML app with session support and DB middleware
app = FastHTML(
    secret_key=settings.secret_key,
    session_cookie="siwes_session",
    middleware=[Middleware(DBSessionMiddleware)]
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
    service_worker=False,  # Faststrap route wrapper bug: serve /sw.js manually below.
    offline_page=True,
)

# Add custom headers after Faststrap and PWA
app.hdrs = app.hdrs + [
    Link(rel="stylesheet", href="/assets/custom.css"),
    Script(src="https://unpkg.com/htmx.org@1.9.10"),
]

# Setup component defaults
setup_siwes_defaults()

# Mount static files for custom CSS and icon
mount_assets(app, "app/presentation/assets", url_path="/assets")


@app.middleware("http")
async def no_store_middleware(request, call_next):
    """Prevent browser caching of app pages so logout/back does not reveal stale protected screens."""
    response = await call_next(request)
    path = request.url.path

    static_prefixes = ("/static/", "/assets/")
    static_exact = {"/manifest.json", "/sw.js", "/favicon.ico", "/health"}
    if path.startswith(static_prefixes) or path in static_exact:
        return response

    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response


@app.get("/sw.js")
def service_worker():
    """Serve service worker script without FastHTML response double-wrapping."""
    sw_path = Path("app/presentation/assets/sw.js")
    return FileResponse(sw_path, media_type="application/javascript")

# Initialize database
init_db()

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
from app.presentation.routes.notifications import register_notification_routes
register_notification_routes(app)
from app.presentation.routes.calls import register_call_routes
register_call_routes(app)
from app.presentation.routes.chat import register_chat_routes
register_chat_routes(app)
from app.presentation.routes.supervisor import setup_supervisor_routes
setup_supervisor_routes(app)
from app.presentation.routes.calls import register_call_routes
register_call_routes(app)


# Health check endpoint
@app.get("/health")
def health_check():
    """Health check endpoint for monitoring."""
    return {"status": "healthy", "service": "siwes-logbook"}


# Run the application
if __name__ == "__main__":
    serve(port=5031)

    """
    Window A (Supervisor)

Login: ada.williams@university.edu.ng / password123
Go to Communication. You should see "John Doe" (or similar) in the list.
Window B (Student)

Login: john.doe@student.university.edu.ng / password123
Go to Communication. You should see "Dr. Ada Williams" in the header."""

