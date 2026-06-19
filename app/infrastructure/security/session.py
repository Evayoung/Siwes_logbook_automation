"""Session management and authentication utilities.

This module provides session management for FastHTML applications, including
user authentication, role-based access control, and session lifecycle management.

Example:
    >>> from app.infrastructure.security.session import create_session, get_current_user
    >>> from fasthtml.common import Request
    >>> 
    >>> # Create a session for a user
    >>> session_data = create_session(user)
    >>> 
    >>> # Get current user from request
    >>> user = get_current_user(request, db)
"""

from typing import Optional, Dict, Any, Callable
from datetime import datetime, timedelta
from functools import wraps
import inspect
from app.infrastructure.database.connection import engine
from app.infrastructure.database.connection import SessionLocal

from fasthtml.common import Request, RedirectResponse
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.domain.models.user import User, UserRole
from app.config import get_settings


def create_session(user: User) -> Dict[str, Any]:
    """Create a session dictionary for a user.
    
    Generates a session data dictionary containing user information for
    storage in FastHTML's session management system.
    
    Args:
        user: The authenticated user to create a session for
    
    Returns:
        Dictionary containing session data with keys:
            - user_id: User's unique identifier
            - email: User's email address
            - role: User's role (student/supervisor)
            - full_name: User's full name
            - created_at: Session creation timestamp
    
    Example:
        >>> session_data = create_session(user)
        >>> print(session_data['user_id'])
        '123e4567-e89b-12d3-a456-426614174000'
    
    Note:
        - Session data should be stored in FastHTML's session cookie
        - Sensitive data (passwords) should never be in session
        - Session expiry is handled by FastHTML configuration
    """
    settings = get_settings()
    
    return {
        'user_id': user.id,
        'email': user.email,
        'role': user.role.value,
        'full_name': user.full_name,
        'created_at': datetime.utcnow().isoformat(),
        'expires_at': (
            datetime.utcnow() + timedelta(hours=settings.session_lifetime_hours)
        ).isoformat(),
    }


def get_current_user(request: Request, db: Session) -> Optional[User]:
    """Get the currently authenticated user from the request.
    
    Retrieves the user object for the currently authenticated session by
    extracting the user_id from the session and querying the database.
    
    Args:
        request: The FastHTML request object containing session data
        db: Database session for querying user data
    
    Returns:
        The authenticated User object, or None if not authenticated
    
    Example:
        >>> user = get_current_user(request, db)
        >>> if user:
        ...     print(f"Logged in as: {user.email}")
        ... else:
        ...     print("Not authenticated")
    
    Note:
        - Returns None if session is missing or expired
        - Returns None if user is not found in database
        - Does not verify session expiry (handled by FastHTML)
    """
    # Get session from request
    session = getattr(request, 'session', None)
    if not session:
        return None
    
    # Extract user_id from session
    user_id = session.get('user_id')
    if not user_id:
        return None
    
    # Check session expiry
    expires_at_str = session.get('expires_at')
    if expires_at_str:
        try:
            expires_at = datetime.fromisoformat(expires_at_str)
            if datetime.utcnow() > expires_at:
                return None
        except (ValueError, TypeError):
            return None
    
    # Defensive fix: Ensure session is bound
    if db.bind is None:
        db.bind = engine
    
    # Query user from database. Supabase pooler connections can be closed
    # between requests; retry once on a fresh session instead of surfacing 500s.
    try:
        return db.query(User).filter(User.id == user_id).first()
    except OperationalError:
        try:
            db.rollback()
            db.close()
        except Exception:
            pass

        retry_db = SessionLocal()
        request.state.db = retry_db
        if retry_db.bind is None:
            retry_db.bind = engine
        return retry_db.query(User).filter(User.id == user_id).first()


def require_auth(redirect_to: str = "/login"):
    """Decorator to require authentication for a route.
    
    Wraps a FastHTML route handler to ensure the user is authenticated.
    If not authenticated, redirects to the login page.
    
    Args:
        redirect_to: URL to redirect to if not authenticated (default: "/login")
    
    Returns:
        Decorator function that wraps route handlers
    
    Example:
        >>> @app.get("/dashboard")
        >>> @require_auth()
        >>> def dashboard(request: Request, db: Session):
        ...     user = get_current_user(request, db)
        ...     return f"Welcome, {user.full_name}!"
    
    Note:
        - The wrapped function must accept 'request' and 'db' parameters
        - Adds 'current_user' to the function's keyword arguments
        - Returns RedirectResponse if authentication fails
    """
    def decorator(func: Callable):
        def _inject_user(args, kwargs):
            # Extract request and db from args/kwargs
            request = kwargs.get('request') or (args[0] if args else None)

            # Try to get db from kwargs/args, then request.state
            db = kwargs.get('db') or (args[1] if len(args) > 1 else None)
            if not db and request and hasattr(request.state, "db"):
                db = request.state.db
                kwargs['db'] = db

            if not request or not db:
                raise ValueError("Route handler must accept 'request' and 'db' parameters")

            user = get_current_user(request, db)
            if not user:
                return None, RedirectResponse(url=redirect_to, status_code=303)

            kwargs['current_user'] = user
            return user, None

        if inspect.iscoroutinefunction(func):
            @wraps(func)
            async def async_wrapper(*args, **kwargs):
                _, redirect = _inject_user(args, kwargs)
                if redirect:
                    return redirect
                return await func(*args, **kwargs)
            return async_wrapper

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            _, redirect = _inject_user(args, kwargs)
            if redirect:
                return redirect
            return func(*args, **kwargs)

        return sync_wrapper
    return decorator


def require_role(*allowed_roles: UserRole, redirect_to: str = "/unauthorized"):
    """Decorator to require specific roles for a route.
    
    Wraps a FastHTML route handler to ensure the user has one of the
    specified roles. If not authorized, redirects to an error page.
    
    Args:
        *allowed_roles: One or more UserRole values that are allowed
        redirect_to: URL to redirect to if not authorized (default: "/unauthorized")
    
    Returns:
        Decorator function that wraps route handlers
    
    Example:
        >>> @app.get("/supervisor/dashboard")
        >>> @require_auth()
        >>> @require_role(UserRole.SUPERVISOR)
        >>> def supervisor_dashboard(request: Request, db: Session, current_user: User):
        ...     return "Supervisor Dashboard"
    
    Note:
        - Should be used together with @require_auth()
        - The wrapped function must have 'current_user' in kwargs
        - Returns RedirectResponse if role check fails
    """
    def decorator(func: Callable):
        if inspect.iscoroutinefunction(func):
            @wraps(func)
            async def async_wrapper(*args, **kwargs):
                user = kwargs.get('current_user')
                if not user:
                    raise ValueError("@require_role must be used with @require_auth")
                if user.role not in allowed_roles:
                    return RedirectResponse(url=redirect_to, status_code=303)
                return await func(*args, **kwargs)
            return async_wrapper

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            user = kwargs.get('current_user')
            if not user:
                raise ValueError("@require_role must be used with @require_auth")
            if user.role not in allowed_roles:
                return RedirectResponse(url=redirect_to, status_code=303)
            return func(*args, **kwargs)

        return sync_wrapper
    return decorator


def clear_session(request: Request) -> None:
    """Clear the current user session.
    
    Removes all session data for the current user, effectively logging
    them out.
    
    Args:
        request: The FastHTML request object containing session data
    
    Example:
        >>> @app.post("/logout")
        >>> def logout(request: Request):
        ...     clear_session(request)
        ...     return RedirectResponse(url="/login")
    
    Note:
        - Clears all session data, not just user-related fields
        - Should be called during logout
    """
    session = getattr(request, 'session', None)
    if session:
        session.clear()
