"""Authentication routes for login and logout.

This module provides route handlers for user authentication,
including login, logout, and session management.
"""

from fasthtml.common import *
from sqlalchemy.orm import Session
from app.presentation.components.domain.auth import LoginPage
from app.presentation.components.domain.landing import LandingPage
from app.application.services.auth import AuthService
from app.domain.models.user import UserRole
from app.infrastructure.security.session import get_current_user


def setup_auth_routes(app: FastHTML):
    """Setup authentication routes.
    
    Args:
        app: FastHTML application instance
    """
    
    def _dashboard_path(role: UserRole) -> str:
        """Resolve dashboard route for a user role."""
        if role == UserRole.STUDENT:
            return "/student/dashboard"
        return "/supervisor/dashboard"

    def _clear_invalid_session(request: Request) -> None:
        """Clear malformed or stale session state."""
        if hasattr(request, "session"):
            request.session.clear()

    @app.get("/")
    def index(request: Request):
        """Route root to dashboard when authenticated, otherwise public landing."""
        db: Session = request.state.db
        user = get_current_user(request, db)
        if user:
            return RedirectResponse(_dashboard_path(user.role), status_code=303)
        _clear_invalid_session(request)
        return LandingPage()
    
    
    @app.get("/login")
    def login_page(request: Request):
        """Display login page.
        
        Args:
            request: FastHTML request object
        
        Returns:
            Login page HTML
        """
        if request.query_params.get("force") in {"1", "true", "yes"}:
            _clear_invalid_session(request)
            return LoginPage()

        db: Session = request.state.db
        user = get_current_user(request, db)
        if user:
            return RedirectResponse(_dashboard_path(user.role), status_code=303)

        if request.session.get("user_id"):
            _clear_invalid_session(request)
        
        return LoginPage()

    @app.get("/unauthorized")
    def unauthorized_page():
        """Unauthorized access page."""
        return Div(
            H1("Unauthorized"),
            P("You do not have permission to access this page."),
            A("Back to Login", href="/login", cls="btn btn-primary"),
            cls="container py-5"
        )
    
    
    @app.post("/login")
    async def login_submit(
        request: Request,
        email: str,
        password: str,
        remember_me: bool = False
    ):
        """Handle login form submission.
        
        Args:
            request: FastHTML request object
            email: User email
            password: User password
            remember_me: Whether to remember the user
        
        Returns:
            Redirect to appropriate dashboard or login page with error
        """
        # Get DB session from middleware
        db: Session = request.state.db
        
        try:
            auth_service = AuthService(db)
            result = auth_service.login(email, password)
            
            # Set session data
            request.session["user_id"] = result["user"].id
            request.session["role"] = result["user"].role.value
            request.session["email"] = result["user"].email
            
            # Always persist explicit session expiry.
            request.session["expires_at"] = result["session"]["expires_at"]
            
            # Redirect based on role
            return RedirectResponse(_dashboard_path(result["user"].role), status_code=303)
                
        except ValueError as e:
            # Login failed - show error
            return LoginPage(error=str(e))
    
    
    @app.get("/logout")
    @app.post("/logout")
    def logout(request: Request):
        """Handle logout.
        
        Args:
            request: FastHTML request object
        
        Returns:
            Redirect to login page
        """
        # Clear session
        request.session.clear()

        return RedirectResponse(
            "/login?force=1&logged_out=1",
            status_code=303,
            headers={
                "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
                "Pragma": "no-cache",
                "Expires": "0",
            },
        )

    @app.get("/switch-account")
    def switch_account(request: Request):
        """Force clear session and return to login form."""
        _clear_invalid_session(request)
        return RedirectResponse("/login?force=1", status_code=303)
