"""Database session middleware.

This module provides middleware to manage database sessions for each request,
attaching the session to request.state.db and ensuring proper cleanup.
"""

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from sqlalchemy.exc import SQLAlchemyError, OperationalError, ProgrammingError
from sqlalchemy.pool.impl import exc as pool_exc
from app.infrastructure.database.connection import SessionLocal, engine

class DBSessionMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = None
        db = None
        try:
            # Create session and attach to request state
            db = SessionLocal()
            
            # Ensure session is bound (fix for UnboundExecutionError)
            if db.bind is None:
                print("DEBUG: Session was unbound. Force-binding to engine.")
                db.bind = engine
                
            request.state.db = db
            
            # Process request
            response = await call_next(request)
            
        except (OperationalError, pool_exc.TimeoutError, ProgrammingError):
            # Handle stale connections by invalidating and retrying
            if db is not None:
                db.invalidate()
            raise
        finally:
            # Close session after request is handled
            if db is not None:
                try:
                    db.close()
                except SQLAlchemyError as exc:
                    print(f"[DB] ignored session close error: {exc}")
                
        return response
