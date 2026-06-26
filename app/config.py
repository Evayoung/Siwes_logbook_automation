"""Application configuration management.

This module handles loading and validating environment variables and
application settings using Pydantic for type safety and validation.
"""

import os
from functools import lru_cache
from typing import Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables.
    
    All settings are loaded from environment variables or .env file.
    Uses Pydantic for automatic validation and type conversion.
    
    Attributes:
        database_url: PostgreSQL connection string for production.
        database_url_dev: SQLite connection string for development.
        secret_key: Secret key for session encryption and security.
        session_lifetime_hours: Session expiration time in hours.
        geofence_default_radius_meters: Default geofence radius.
        geofence_tolerance_meters: GPS accuracy tolerance buffer.
        debug: Enable debug mode (verbose logging, auto-reload).
        host: Server bind address.
        port: Server port number.
        environment: Deployment environment (development/production).
    
    Example:
        >>> settings = get_settings()
        >>> print(settings.database_url)
        postgresql://user:pass@localhost/siwes_db
    """
    
    # Database
    database_url: str = Field(
        default="sqlite:///./siwes_dev.db",
        description="PostgreSQL connection URL for production"
    )
    database_url_dev: str = Field(
        default="sqlite:///./siwes_dev.db",
        description="SQLite connection URL for development"
    )
    supabase_url: Optional[str] = Field(
        default=None,
        description="Supabase PostgreSQL connection URL"
    )
    neon_url: Optional[str] = Field(
        default=None,
        description="Neon PostgreSQL serverless connection URL"
    )
    
    # Security
    secret_key: str = Field(
        ...,
        min_length=32,
        description="Secret key for session encryption (min 32 chars)"
    )
    session_lifetime_hours: int = Field(
        default=24,
        ge=1,
        le=168,
        description="Session expiration time (1-168 hours)"
    )
    offline_login_grace_days: int = Field(
        default=7,
        ge=1,
        le=30,
        description="How many days offline cached login resume is allowed after last successful online auth"
    )
    offline_sync_grace_days: int = Field(
        default=14,
        ge=1,
        le=180,
        description="How many days an offline-created log may wait before syncing"
    )
    
    # Geofencing
    geofence_default_radius_meters: int = Field(
        default=500,
        ge=50,
        le=5000,
        description="Default geofence radius (50-5000 meters)"
    )
    geofence_tolerance_meters: int = Field(
        default=50,
        ge=0,
        le=200,
        description="GPS accuracy tolerance (0-200 meters)"
    )
    
    call_ring_timeout_seconds: int = Field(
        default=75,
        ge=15,
        le=300,
        description="Seconds before unanswered ringing call is auto-marked as missed"
    )
    
    # LiveKit
    livekit_url: Optional[str] = Field(
        default=None,
        description="LiveKit server URL (wss://...)"
    )
    livekit_api_key: Optional[str] = Field(
        default=None,
        description="LiveKit API key"
    )
    livekit_api_secret: Optional[str] = Field(
        default=None,
        description="LiveKit API secret"
    )
    
    # Application
    debug: bool = Field(
        default=False,
        description="Enable debug mode"
    )
    host: str = Field(
        default="0.0.0.0",
        description="Server bind address"
    )
    port: int = Field(
        default=8000,
        ge=1024,
        le=65535,
        description="Server port (1024-65535)"
    )
    environment: str = Field(
        default="development",
        description="Deployment environment"
    )
    auto_init_db: bool = Field(
        default=False,
        description="Run create_all/schema patches during app startup. Keep false in production."
    )
    db_pool_size: int = Field(
        default=5,
        ge=1,
        le=20,
        description="SQLAlchemy pool size for PostgreSQL deployments"
    )
    db_max_overflow: int = Field(
        default=5,
        ge=0,
        le=50,
        description="SQLAlchemy max overflow connections for PostgreSQL deployments"
    )
    db_disable_pooling: bool = Field(
        default=False,
        description="Disable SQLAlchemy connection pooling. False=use pool (for direct connections). True=NullPool (for pgbouncer transaction mode)."
    )
    
    app_name: str = Field(
        default="SIWES Logbook Automation System",
    )

    @field_validator("secret_key")
    @classmethod
    def validate_secret_key(cls, v: str) -> str:
        """Validate secret key is not a default/example value.
        
        Args:
            v: Secret key value to validate.
        
        Returns:
            Validated secret key.
        
        Raises:
            ValueError: If secret key contains 'change' or 'example'.
        """
        if "change" in v.lower() or "example" in v.lower():
            raise ValueError(
                "Secret key must be changed from example value. "
                "Generate with: python -c 'import secrets; print(secrets.token_hex(32))'"
            )
        return v

    @field_validator("debug", mode="before")
    @classmethod
    def normalize_debug(cls, v: object) -> object:
        """Accept common deployment labels for DEBUG."""
        if isinstance(v, str) and v.strip().lower() in {"release", "prod", "production"}:
            return False
        return v
    
    @property
    def db_url(self) -> str:
        """Get appropriate database URL based on environment.
        
        Priority: NEON_URL > SUPABASE_URL > DATABASE_URL > DATABASE_URL_DEV
        
        Returns:
            PostgreSQL URL for production, SQLite for development.
        """
        if self.environment == "production" and self.neon_url:
            return self._normalize_database_url(self.neon_url)
        if self.environment == "production" and self.supabase_url:
            return self._normalize_database_url(self.supabase_url)
        if self.environment == "production":
            return self._normalize_database_url(self.database_url)
        return self._normalize_database_url(self.database_url_dev)

    @staticmethod
    def _normalize_database_url(url: str) -> str:
        """Normalize external Postgres URLs for SQLAlchemy.
    
        The 5432->6543 port conversion ONLY applies to Supabase pooler URLs
        (aws-*.pooler.supabase.com).  Neon and direct connection URLs
        must keep port 5432.
        """
        if url.startswith("postgres://"):
            url = "postgresql://" + url[len("postgres://"):]
        # Only convert pooler URLs to transaction-mode port 6543.
        # Direct db.*.supabase.co connections must stay on 5432.
        if ".pooler.supabase.com:5432" in url:
            url = url.replace(".pooler.supabase.com:5432", ".pooler.supabase.com:6543")
        # Add sslmode=require for Supabase URLs that don't have it
        if "supabase" in url.lower() and "sslmode=" not in url.lower():
            separator = "&" if "?" in url else "?"
            return f"{url}{separator}sslmode=require"
        # Add sslmode=require for Neon URLs that don't have it
        if "neon.tech" in url.lower() and "sslmode=" not in url.lower():
            separator = "&" if "?" in url else "?"
            return f"{url}{separator}sslmode=require"
        return url
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache()
def get_settings() -> Settings:
    """Get cached application settings instance.
    
    Settings are loaded once and cached for application lifetime.
    Uses lru_cache to ensure single instance across application.
    
    Returns:
        Singleton Settings instance.
    
    Example:
        >>> settings = get_settings()
        >>> print(f"Running on port {settings.port}")
        Running on port 8000
    """
    return Settings()
