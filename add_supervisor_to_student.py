"""Migration script to add assigned_supervisor_id to student_profiles.
"""
import sys
import os
from sqlalchemy import text
from app.infrastructure.database.connection import get_db_session

# Add project root to path
sys.path.append(os.getcwd())

def migrate():
    print("Migrating: Adding assigned_supervisor_id to student_profiles...")
    db = get_db_session()
    try:
        # Check if column exists
        check_sql = text("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name='student_profiles' AND column_name='assigned_supervisor_id'
        """)
        result = db.execute(check_sql).fetchone()
        
        if not result:
            # Add column
            sql = text("""
                ALTER TABLE student_profiles 
                ADD COLUMN assigned_supervisor_id VARCHAR(36) 
                REFERENCES users(id);
            """)
            db.execute(sql)
            db.commit()
            print("Successfully added assigned_supervisor_id column.")
        else:
            print("Column assigned_supervisor_id already exists.")
            
    except Exception as e:
        print(f"Error migrating: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    migrate()
