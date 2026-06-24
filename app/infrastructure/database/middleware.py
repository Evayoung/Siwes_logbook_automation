"""Database session middleware.

This module provides middleware to manage database sessions for each request,
attaching the session to request.state.db and ensuring proper cleanup.
"""

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request, ClientDisconnect
from starlette.responses import Response
from sqlalchemy.exc import SQLAlchemyError, OperationalError, ProgrammingError
from sqlalchemy.pool.impl import exc as pool_exc
from app.infrastructure.database.connection import SessionLocal, engine


class DBSessionMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        db = None
        try:
            db = SessionLocal()
            if db.bind is None:
                db.bind = engine
            request.state.db = db
            response = await call_next(request)
            return response

        except ClientDisconnect:
            print("[DB Middleware] Client disconnected.")
            return Response("Client Disconnected", status_code=499)

        except (OperationalError, pool_exc.TimeoutError) as exc:
            # Stale / dropped connection — try once with a fresh session.
            print(f"[DB] stale connection, retrying: {exc}")
            if db is not None:
                try:
                    db.invalidate()
                    db.close()
                except Exception:
                    pass

            try:
                db = SessionLocal()
                if db.bind is None:
                    db.bind = engine
                request.state.db = db
                response = await call_next(request)
                return response
            except Exception as retry_exc:
                print(f"[DB] retry also failed: {retry_exc}")
                return Response("Service temporarily unavailable", status_code=503)

        except ProgrammingError as exc:
            # pool_pre_ping fired "set_session cannot be used inside a transaction"
            # This means a connection was returned to the pool with an open txn.
            # Invalidate and open a brand-new connection.
            print(f"[DB] ProgrammingError (pre-ping txn conflict), retrying: {exc}")
            if db is not None:
                try:
                    db.invalidate()
                    db.close()
                except Exception:
                    pass

            try:
                db = SessionLocal()
                if db.bind is None:
                    db.bind = engine
                request.state.db = db
                response = await call_next(request)
                return response
            except Exception as retry_exc:
                print(f"[DB] retry also failed: {retry_exc}")
                return Response("Service temporarily unavailable", status_code=503)

        finally:
            if db is not None:
                try:
                    db.close()
                except SQLAlchemyError as exc:
                    print(f"[DB] ignored session close error: {exc}")
