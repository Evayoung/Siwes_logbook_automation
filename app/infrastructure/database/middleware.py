"""Database session middleware.

This module provides middleware to manage database sessions for each request,
attaching the session to request.state.db and ensuring proper cleanup.
"""

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from sqlalchemy.exc import SQLAlchemyError
from app.infrastructure.database.connection import SessionLocal, engine

class DBSessionMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = None
        try:
            # Create session and attach to request state
            session = SessionLocal()
            
            # Ensure session is bound (fix for UnboundExecutionError)
            if session.bind is None:
                print("DEBUG: Session was unbound. Force-binding to engine.")
                session.bind = engine
                
            request.state.db = session
            
            # Process request
            response = await call_next(request)
            
        finally:
            # Close session after request is handled
            if hasattr(request.state, "db"):
                try:
                    request.state.db.close()
                except SQLAlchemyError as exc:
                    print(f"[DB] ignored session close error: {exc}")
                
        return response
