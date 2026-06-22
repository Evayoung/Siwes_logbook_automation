"""Session management and authentication utilities.

This module provides session management for FastHTML applications, including
user authentication, role-based access control, and session lifecycle management.
"""

from typing import Optional, Dict, Any, Callable
from datetime import datetime, timedelta
from functools import wraps
import inspect

from app.infrastructure.database.connection import engine, SessionLocal
from fasthtml.common import Request, RedirectResponse
from starlette.responses import Response as StarletteResponse
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.domain.models.user import User, UserRole
from app.config import get_settings


def create_session(user: User) -> Dict[str, Any]:
    """Create a session dictionary for a user."""
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
    """Get the currently authenticated user from the request."""
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

        try:
            retry_db = SessionLocal()
            request.state.db = retry_db
            if retry_db.bind is None:
                retry_db.bind = engine
            return retry_db.query(User).filter(User.id == user_id).first()
        except OperationalError:
            # Do NOT clear the session here — that would log the user out.
            # A transient DB error does not mean the session is invalid.
            # Return None so this single request fails gracefully; the user
            # can simply retry and will still be logged in.
            try:
                retry_db.close()
            except Exception:
                pass
            return None


def require_auth(redirect_to: str = "/login"):
    """Decorator to require authentication for a route.

    If the request comes from HTMX (HX-Request header), returns an
    HX-Redirect response instead of HTTP 303 so the browser performs a
    full-page navigation to /login rather than injecting the login page
    HTML inside the HTMX target element (which looks like a logout).
    """
    def decorator(func: Callable):
        def _inject_user(args, kwargs):
            request = kwargs.get('request') or (args[0] if args else None)

            db = kwargs.get('db') or (args[1] if len(args) > 1 else None)
            if not db and request and hasattr(request.state, "db"):
                db = request.state.db
                kwargs['db'] = db

            if not request or not db:
                raise ValueError("Route handler must accept 'request' and 'db' parameters")

            user = get_current_user(request, db)
            if not user:
                # For HTMX requests use HX-Redirect so the browser does a
                # proper full-page navigation instead of swapping /login HTML
                # into the HTMX target (which makes it look like a logout).
                is_htmx = request.headers.get("HX-Request") == "true"
                if is_htmx:
                    resp = StarletteResponse(
                        content="",
                        status_code=200,
                        headers={"HX-Redirect": redirect_to},
                    )
                    return None, resp
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

    Must be used together with @require_auth().
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
    """Clear the current user session (logout)."""
    session = getattr(request, 'session', None)
    if session:
        session.clear()
