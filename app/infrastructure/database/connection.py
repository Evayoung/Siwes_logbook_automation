"""Database connection and session management.

This module handles SQLAlchemy engine creation, session factory setup,
and provides utilities for database connection management.
"""

import time
from contextlib import contextmanager
from typing import Generator, TypeVar, Callable

from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import NullPool, StaticPool
from sqlalchemy.exc import OperationalError, ProgrammingError
from sqlalchemy.pool.impl import exc as pool_exc

from app.config import get_settings
from app.domain.models.base import Base

# Import all models to ensure they're registered with Base.metadata
from app.domain.models import *

T = TypeVar('T')


def execute_with_retry(fn: Callable[[], T], max_retries: int = 3) -> T:
    """Execute a database operation with retry on transient SSL/connection errors.

    Args:
        fn: Function to execute that may raise OperationalError or TimeoutError
        max_retries: Maximum number of retry attempts (default 3)

    Returns:
        Result of the function call

    Raises:
        OperationalError: If all retries fail
        TimeoutError: If connection pool timeout after all retries
        ProgrammingError: If PostgreSQL rejects autocommit during ping
    """
    last_error = None
    for attempt in range(max_retries + 1):
        try:
            return fn()
        except (OperationalError, pool_exc.TimeoutError) as e:
            last_error = e
            err_str = str(e).lower()
            is_ssl_error = "ssl" in err_str and "closed" in err_str
            if attempt < max_retries:
                delay = 0.5 * (2 ** attempt)
                if is_ssl_error or attempt > 0:
                    delay *= 2  # longer backoff for SSL / repeated failures
                time.sleep(delay)
                continue
            raise
        except ProgrammingError as e:
            # ProgrammingErrors are usually schema issues, not transient
            raise
    raise last_error  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Engine setup
# ---------------------------------------------------------------------------

settings = get_settings()
DATABASE_URL = settings.db_url

if DATABASE_URL.startswith("sqlite"):
    # SQLite for local development
    engine = create_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        echo=settings.debug,
    )

    @event.listens_for(Engine, "connect")
    def set_sqlite_pragma(dbapi_conn, connection_record):
        """Enable foreign key constraints for SQLite connections."""
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

else:
    # Determine if we are connecting through a transaction-mode pooler (e.g. PgBouncer)
    # Neon (neon.tech) is serverless PostgreSQL — treat as NullPool to avoid idle SSL drops.
    is_pooler = (
        "pooler.supabase.com" in DATABASE_URL
        or "neon.tech" in DATABASE_URL
        or (":6543" in DATABASE_URL and "neon.tech" not in DATABASE_URL)
    )

    if is_pooler:
        # PgBouncer in transaction mode does not support session parameters/autocommit modifications
        # like pool_pre_ping, and connection pooling must be handled by the server (NullPool locally).
        # TCP keepalives are still needed to prevent Supabase from dropping idle SSL connections.
        print("[DB] Transaction-mode pooler or Neon detected. Using NullPool with TCP keepalives.")
        engine_kwargs = {
            "poolclass": NullPool,
            "connect_args": {
                "connect_timeout": 10,
                "keepalives": 1,
                "keepalives_idle": 30,
                "keepalives_interval": 10,
                "keepalives_count": 5,
            },
            "echo": settings.debug,
        }
    else:
        # Direct DB connection supports connection pooling and pre-ping
        print("[DB] Direct database connection detected. Enabling pooling & pool_pre_ping.")
        engine_kwargs = {
            "pool_pre_ping": True,        # detect & reconnect stale connections automatically
            "pool_recycle": 300,           # recycle connections every 5 minutes
            "connect_args": {
                "connect_timeout": 10,     # fail fast on dead connections (not hang)
                "keepalives": 1,
                "keepalives_idle": 30,
                "keepalives_interval": 10,
                "keepalives_count": 3,
            },
            "echo": settings.debug,
        }
        if settings.db_disable_pooling:
            engine_kwargs["poolclass"] = NullPool
        else:
            engine_kwargs["pool_size"] = settings.db_pool_size
            engine_kwargs["max_overflow"] = settings.db_max_overflow

    engine = create_engine(DATABASE_URL, **engine_kwargs)



# Session factory
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)


# ---------------------------------------------------------------------------
# DB initialisation helpers
# ---------------------------------------------------------------------------

def init_db() -> None:
    """Initialize database by creating all tables.

    Creates all tables defined in SQLAlchemy models. Should be called
    once during application startup or via migration scripts.

    Example:
        >>> from app.infrastructure.database.connection import init_db
        >>> init_db()
        # All tables created

    Note:
        In production, use Alembic migrations instead of this function.
        This is primarily for development and testing.
    """
    Base.metadata.create_all(bind=engine)
    _apply_schema_patches()


def _apply_schema_patches() -> None:
    """Apply safe, idempotent schema patches for known drift issues.

    This project currently uses script-based migrations in development.
    These patches keep existing databases aligned with ORM models.
    """
    inspector = inspect(engine)
    table_names = set(inspector.get_table_names())
    patches: list[str] = []

    if "notification_broadcasts" not in table_names:
        if engine.name == "sqlite":
            patches.append(
                "CREATE TABLE notification_broadcasts ("
                "id INTEGER PRIMARY KEY AUTOINCREMENT,"
                "user_id VARCHAR(36) NOT NULL,"
                "event_type VARCHAR(50) NOT NULL,"
                "data TEXT NOT NULL,"
                "created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP"
                ")"
            )
        else:
            patches.append(
                "CREATE TABLE notification_broadcasts ("
                "id SERIAL PRIMARY KEY,"
                "user_id VARCHAR(36) NOT NULL,"
                "event_type VARCHAR(50) NOT NULL,"
                "data TEXT NOT NULL,"
                "created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP"
                ")"
            )
        patches.append("CREATE INDEX ix_notification_broadcasts_user_id ON notification_broadcasts (user_id)")
        patches.append("CREATE INDEX ix_notification_broadcasts_created_at ON notification_broadcasts (created_at)")

    if "call_logs" in table_names:
        call_log_columns = {c["name"] for c in inspector.get_columns("call_logs")}
        if "notified_at" not in call_log_columns:
            patches.append("ALTER TABLE call_logs ADD COLUMN notified_at TIMESTAMP NULL")
        if "call_type" not in call_log_columns:
            patches.append("ALTER TABLE call_logs ADD COLUMN call_type VARCHAR(10) DEFAULT 'video' NOT NULL")
        if "notes" not in call_log_columns:
            patches.append("ALTER TABLE call_logs ADD COLUMN notes TEXT NULL")

    if "student_profiles" in table_names:
        student_profile_columns = {c["name"] for c in inspector.get_columns("student_profiles")}
        if "setting_location_service" not in student_profile_columns:
            patches.append("ALTER TABLE student_profiles ADD COLUMN setting_location_service BOOLEAN NOT NULL DEFAULT TRUE")
        if "setting_offline_mode" not in student_profile_columns:
            patches.append("ALTER TABLE student_profiles ADD COLUMN setting_offline_mode BOOLEAN NOT NULL DEFAULT FALSE")
        if "setting_notifications" not in student_profile_columns:
            patches.append("ALTER TABLE student_profiles ADD COLUMN setting_notifications BOOLEAN NOT NULL DEFAULT TRUE")

    if "daily_logs" in table_names:
        daily_log_columns = {c["name"] for c in inspector.get_columns("daily_logs")}
        if "created_offline_at" not in daily_log_columns:
            patches.append("ALTER TABLE daily_logs ADD COLUMN created_offline_at TIMESTAMP NULL")

    if patches:
        with engine.begin() as conn:
            for ddl in patches:
                conn.execute(text(ddl))

    if "daily_logs" in table_names:
        index_names = {idx["name"] for idx in inspector.get_indexes("daily_logs")}
        if "uq_daily_logs_student_date" not in index_names:
            with engine.begin() as conn:
                conn.execute(
                    text(
                        "CREATE UNIQUE INDEX uq_daily_logs_student_date "
                        "ON daily_logs (student_id, log_date)"
                    )
                )

    # Composite indexes for production query performance
    composite_indexes = [
        ("chat_messages", "ix_chat_messages_sender_receiver_created",
         "CREATE INDEX IF NOT EXISTS ix_chat_messages_sender_receiver_created "
         "ON chat_messages (sender_id, receiver_id, created_at)"),
        ("chat_messages", "ix_chat_messages_receiver_unread_created",
         "CREATE INDEX IF NOT EXISTS ix_chat_messages_receiver_unread_created "
         "ON chat_messages (receiver_id, is_read, created_at)"),
        ("notifications", "ix_notifications_user_unread_created",
         "CREATE INDEX IF NOT EXISTS ix_notifications_user_unread_created "
         "ON notifications (user_id, is_read, created_at)"),
        ("call_logs", "ix_call_logs_student_supervisor_status_started",
         "CREATE INDEX IF NOT EXISTS ix_call_logs_student_supervisor_status_started "
         "ON call_logs (student_id, supervisor_id, status, started_at)"),
    ]
    for tbl, idx_name, ddl in composite_indexes:
        if tbl in table_names:
            existing = {idx["name"] for idx in inspector.get_indexes(tbl)}
            if idx_name not in existing:
                with engine.begin() as conn:
                    conn.execute(text(ddl))


def drop_db() -> None:
    """Drop all database tables.

    WARNING: This will delete all data! Only use in development/testing.

    Example:
        >>> from app.infrastructure.database.connection import drop_db
        >>> drop_db()
        # All tables and data deleted

    Raises:
        RuntimeError: If called in production environment.
    """
    if settings.environment == "production":
        raise RuntimeError("Cannot drop database in production environment!")
    Base.metadata.drop_all(bind=engine)


@contextmanager
def get_db() -> Generator[Session, None, None]:
    """Get database session with automatic cleanup.

    Provides a database session that automatically commits on success
    and rolls back on error. Session is closed after use.

    Yields:
        SQLAlchemy Session instance.

    Example:
        >>> from app.infrastructure.database.connection import get_db
        >>>
        >>> with get_db() as db:
        ...     user = db.query(User).filter_by(email="test@example.com").first()
        ...     print(user.email)
        test@example.com

    Note:
        For FastHTML routes, use dependency injection instead:
        ```python
        @app.get("/users")
        def get_users(db: Session = Depends(get_db)):
            return db.query(User).all()
        ```
    """
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def get_db_session() -> Session:
    """Get a new database session.

    Returns a new session that must be manually closed by the caller.
    Prefer using get_db() context manager for automatic cleanup.

    Returns:
        SQLAlchemy Session instance.

    Example:
        >>> from app.infrastructure.database.connection import get_db_session
        >>>
        >>> db = get_db_session()
        >>> try:
        ...     users = db.query(User).all()
        ... finally:
        ...     db.close()

    Note:
        Remember to close the session when done to avoid connection leaks.
    """
    return SessionLocal()
