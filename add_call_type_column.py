"""Migration script to add call_type column to call_logs table.
"""
from sqlalchemy import text
from app.infrastructure.database.connection import engine

def add_call_type_column():
    print("Adding call_type column to call_logs table...")
    with engine.connect() as conn:
        try:
            conn.execute(text("ALTER TABLE call_logs ADD COLUMN call_type VARCHAR(10) DEFAULT 'video' NOT NULL"))
            conn.commit()
            print("Column added successfully.")
        except Exception as e:
            if "duplicate column name" in str(e).lower():
                print("Column already exists.")
            else:
                print(f"Error adding column: {e}")

if __name__ == "__main__":
    add_call_type_column()
