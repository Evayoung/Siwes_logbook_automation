"""One-off migration helper for call_logs schema drift.

Adds missing columns used by the ORM model:
- notified_at
- call_type
- notes
"""

from sqlalchemy import inspect, text

from app.infrastructure.database.connection import engine


def add_missing_call_log_columns() -> None:
    inspector = inspect(engine)
    if "call_logs" not in inspector.get_table_names():
        print("call_logs table not found; nothing to patch.")
        return

    existing = {c["name"] for c in inspector.get_columns("call_logs")}
    patches: list[str] = []

    if "notified_at" not in existing:
        patches.append("ALTER TABLE call_logs ADD COLUMN notified_at TIMESTAMP NULL")
    if "call_type" not in existing:
        patches.append("ALTER TABLE call_logs ADD COLUMN call_type VARCHAR(10) DEFAULT 'video' NOT NULL")
    if "notes" not in existing:
        patches.append("ALTER TABLE call_logs ADD COLUMN notes TEXT NULL")

    if not patches:
        print("call_logs schema already up to date.")
        return

    print("Applying call_logs schema patches...")
    with engine.begin() as conn:
        for ddl in patches:
            print(f" - {ddl}")
            conn.execute(text(ddl))
    print("Done.")


if __name__ == "__main__":
    add_missing_call_log_columns()
