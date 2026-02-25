"""Script to check the state of the database, specifically student-supervisor links.
"""
import sys
import os
from sqlalchemy import text
from app.infrastructure.database.connection import get_db_session
from app.domain.models.user import User, UserRole, StudentProfile

# Add project root to path
sys.path.append(os.getcwd())

def check_data():
    print("Checking Database State...")
    db = get_db_session()
    try:
        # 1. Check Supervisors
        supervisors = db.query(User).filter(User.role == UserRole.SUPERVISOR).all()
        print(f"\nFound {len(supervisors)} Supervisors:")
        for sup in supervisors:
            print(f"  - {sup.full_name} ({sup.email}) ID: {sup.id}")

        # 2. Check Students and their Assignments
        students = db.query(User).filter(User.role == UserRole.STUDENT).all()
        print(f"\nFound {len(students)} Students:")
        for stu in students:
            profile = db.query(StudentProfile).filter(StudentProfile.user_id == stu.id).first()
            supervisor_name = "None"
            if profile and profile.assigned_supervisor_id:
                sup = db.query(User).filter(User.id == profile.assigned_supervisor_id).first()
                if sup:
                    supervisor_name = sup.full_name
            
            print(f"  - {stu.full_name} ({stu.email})")
            print(f"    - Profile: {'Found' if profile else 'Missing'}")
            print(f"    - Assigned Supervisor ID: {profile.assigned_supervisor_id if profile else 'N/A'}")
            print(f"    - Supervisor Name: {supervisor_name}")
            
    except Exception as e:
        print(f"Error checking data: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    check_data()
