import sys
from pathlib import Path

from sqlalchemy import text

# Setup path (project root)
current_dir = Path(__file__).resolve().parent
project_root = current_dir.parent
sys.path.append(str(project_root))

from app.infrastructure.database.connection import engine
from app.domain.models.base import Base
# Import all models to ensure metadata is populated
from app.domain.models import *
from seed_real_data import seed_data


def reset():
    print("Dropping all tables...")
    try:
        Base.metadata.drop_all(bind=engine)
        print("[OK] Tables dropped.")
    except Exception as e:
        dialect_name = getattr(getattr(engine, "dialect", None), "name", "")
        if dialect_name == "postgresql":
            print(f"[WARN] Standard drop failed, using PostgreSQL CASCADE reset: {e}")
            try:
                with engine.begin() as conn:
                    conn.execute(text("DROP SCHEMA IF EXISTS public CASCADE"))
                    conn.execute(text("CREATE SCHEMA public"))
                    conn.execute(text("GRANT ALL ON SCHEMA public TO public"))
                print("[OK] PostgreSQL schema reset complete.")
            except Exception as inner:
                print(f"[ERROR] Error resetting PostgreSQL schema: {inner}")
                return
        else:
            print(f"[ERROR] Error dropping tables: {e}")
            return

    print("Re-seeding database...")
    try:
        seed_data()
        print("[OK] Reset complete!")
    except Exception as e:
        print(f"[ERROR] Error during reset: {e}")


if __name__ == "__main__":
    reset()
