"""Initialize the Supabase PostgreSQL database for this project.

Usage:
    python scripts/migrate_to_supabase.py
    python scripts/migrate_to_supabase.py --seed
    python scripts/migrate_to_supabase.py --reset --seed
"""

import argparse
import os
import sys
from pathlib import Path

from sqlalchemy import text


current_dir = Path(__file__).resolve().parent
project_root = current_dir.parent
sys.path.append(str(project_root))

APP_TABLES = {
    "users",
    "student_profiles",
    "supervisor_profiles",
    "industrial_placements",
    "geofences",
    "daily_logs",
    "chat_messages",
    "notifications",
    "call_logs",
}

POSTGRES_ENUM_TYPES = (
    "notificationtype",
    "locationstatus",
    "logstatus",
    "userrole",
)


def _load_dotenv_key(path: Path, key: str) -> str | None:
    if not path.exists():
        return None
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, value = line.split("=", 1)
        if name.strip().lower() != key.lower():
            continue
        return value.strip().strip('"').strip("'")
    return None


def _configure_supabase_environment() -> str:
    supabase_url = os.getenv("SUPABASE_URL") or _load_dotenv_key(project_root / ".env", "SUPABASE_URL")
    if not supabase_url:
        raise RuntimeError("SUPABASE_URL is missing. Add the Supabase PostgreSQL connection string to .env.")

    if supabase_url.startswith("postgres://"):
        supabase_url = "postgresql://" + supabase_url[len("postgres://"):]

    if not supabase_url.startswith("postgresql://"):
        raise RuntimeError("SUPABASE_URL must be a PostgreSQL connection string, not the https project API URL.")

    if "supabase" in supabase_url.lower() and "sslmode=" not in supabase_url.lower():
        separator = "&" if "?" in supabase_url else "?"
        supabase_url = f"{supabase_url}{separator}sslmode=require"

    os.environ["ENVIRONMENT"] = "production"
    os.environ["SUPABASE_URL"] = supabase_url
    os.environ["DATABASE_URL"] = supabase_url
    return supabase_url


def _reset_public_schema(engine) -> None:
    with engine.begin() as conn:
        conn.execute(text("DROP SCHEMA IF EXISTS public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))
        conn.execute(text("GRANT ALL ON SCHEMA public TO postgres"))
        conn.execute(text("GRANT ALL ON SCHEMA public TO public"))


def _repair_orphan_enum_types(engine) -> None:
    """Remove enum types left behind by an interrupted empty-schema migration."""
    with engine.begin() as conn:
        existing_tables = {
            row[0]
            for row in conn.execute(
                text(
                    """
                    SELECT tablename
                    FROM pg_tables
                    WHERE schemaname = 'public'
                    """
                )
            )
        }

        if existing_tables.intersection(APP_TABLES):
            return

        existing_types = {
            row[0]
            for row in conn.execute(
                text(
                    """
                    SELECT typname
                    FROM pg_type
                    JOIN pg_namespace ON pg_namespace.oid = pg_type.typnamespace
                    WHERE pg_namespace.nspname = 'public'
                    """
                )
            )
        }

        for type_name in POSTGRES_ENUM_TYPES:
            if type_name in existing_types:
                conn.execute(text(f"DROP TYPE IF EXISTS public.{type_name} CASCADE"))


def main() -> None:
    parser = argparse.ArgumentParser(description="Initialize and optionally seed the Supabase database.")
    parser.add_argument("--reset", action="store_true", help="Drop and recreate the public schema before creating tables.")
    parser.add_argument("--seed", action="store_true", help="Seed realistic demo data after tables are created.")
    args = parser.parse_args()

    _configure_supabase_environment()

    from app.infrastructure.database.connection import engine, init_db

    print("Target database: Supabase PostgreSQL")

    if args.reset:
        print("Resetting public schema...")
        _reset_public_schema(engine)
        print("[OK] Schema reset complete.")
    else:
        _repair_orphan_enum_types(engine)

    print("Creating/updating tables...")
    init_db()
    print("[OK] Tables are ready.")

    if args.seed:
        from seed_real_data import seed_data

        print("Seeding data...")
        seed_data()
        print("[OK] Seed data loaded.")


if __name__ == "__main__":
    main()
