"""Database connection and session management.

This module handles SQLAlchemy engine creation, session factory setup,
and provides utilities for database connection management.
"""

from contextlib import contextmanager
from typing import Generator

from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import NullPool, StaticPool

from app.config import get_settings
from app.domain.models.base import Base

# Import all models to ensure they're registered with Base.metadata
from app.domain.models import *


# Get database URL from settings
settings = get_settings()
DATABASE_URL = settings.db_url

# Create engine with appropriate configuration
if DATABASE_URL.startswith("sqlite"):
    # SQLite configuration for development
    engine = create_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        echo=settings.debug,
    )
    
    # Enable foreign key constraints for SQLite
    @event.listens_for(Engine, "connect")
    def set_sqlite_pragma(dbapi_conn, connection_record):
        """Enable foreign key constraints for SQLite connections.
        
        Args:
            dbapi_conn: Database API connection object.
            connection_record: Connection record (unused).
        """
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()
else:
    # PostgreSQL configuration for production
    engine_kwargs = {
        "pool_pre_ping": True,
        "echo": settings.debug,
    }
    if settings.db_disable_pooling:
        engine_kwargs["poolclass"] = NullPool
    else:
        engine_kwargs["pool_size"] = settings.db_pool_size
        engine_kwargs["max_overflow"] = settings.db_max_overflow

    engine = create_engine(DATABASE_URL, **engine_kwargs)

# Create session factory
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)


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
