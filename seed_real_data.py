"""Script to seed realistic data into the database.
Reads from data/students.json and data/supervisors.json to populate users and placements.
"""

import json
import os
import sys
from datetime import datetime
from sqlalchemy.orm import Session

# Add project root to path
sys.path.append(os.getcwd())

from app.infrastructure.database.connection import get_db_session
from app.domain.models.user import User, UserRole, StudentProfile, SupervisorProfile
from app.domain.models.placement import IndustrialPlacement, Geofence
from app.infrastructure.security.password import hash_password as get_password_hash

def seed_data():
    db = get_db_session()
    try:
        print("Seeding realistic data...")
        
        # 1. Load Data
        with open("data/supervisors.json", "r") as f:
            supervisors_data = json.load(f)
            
        with open("data/students.json", "r") as f:
            students_data = json.load(f)
            
        # 2. Seed Supervisors
        supervisor_map = {}  # email -> user object
        print(f"Creating {len(supervisors_data)} supervisors...")
        
        for sup_data in supervisors_data:
            existing = db.query(User).filter(User.email == sup_data["email"]).first()
            if not existing:
                # Create Supervisor User
                hashed = get_password_hash(sup_data["password"])
                supervisor = User(
                    full_name=sup_data["full_name"],
                    email=sup_data["email"],
                    password_hash=hashed,
                    role=UserRole.SUPERVISOR,
                    is_active=sup_data["is_active"]
                )
                db.add(supervisor)
                db.flush()  # Get ID

                # Create Supervisor Profile
                # Generate a mock staff ID if not provided
                staff_id = f"STAFF/{datetime.now().year}/{str(hash(sup_data['email']))[:4]}"
                profile = SupervisorProfile(
                    user_id=supervisor.id,
                    staff_id=staff_id,
                    faculty="Science"  # Default for now
                )
                db.add(profile)
                
                supervisor_map[supervisor.email] = supervisor
                print(f"  Created supervisor: {supervisor.full_name}")
            else:
                supervisor_map[existing.email] = existing
                print(f"  Supervisor already exists: {existing.full_name}")
        
        db.commit()
        
        # 3. Seed Students and Placements
        print(f"Creating {len(students_data)} students and placements...")
        
        for stud_data in students_data:
            existing_student = db.query(User).filter(User.email == stud_data["email"]).first()
            
            if not existing_student:
                # Create Student User
                hashed = get_password_hash(stud_data["password"])
                student = User(
                    full_name=stud_data["full_name"],
                    email=stud_data["email"],
                    password_hash=hashed,
                    role=UserRole.STUDENT,
                    is_active=stud_data["is_active"]
                )
                db.add(student)
                db.flush()

                # Create Student Profile
                profile = StudentProfile(
                    user_id=student.id,
                    matriculation_number=stud_data["matric_number"],
                    department=stud_data["department"],
                    institution="University of Lagos",  # Default
                    siwes_start_date=datetime(2024, 3, 1).date(),
                    siwes_end_date=datetime(2024, 8, 31).date()
                )
                db.add(profile)
                
                print(f"  Created student: {student.full_name}")
                
                # Create Placement and Geofence
                placement_data = stud_data.get("placement")
                if placement_data:
                    # Find assigned supervisor
                    supervisor_email = stud_data.get("supervisor_email")
                    supervisor = supervisor_map.get(supervisor_email)
                    
                    if supervisor:
                        # Create Geofence first (Required)
                        geofence = Geofence(
                            latitude=6.5244,  # Mock lat
                            longitude=3.3792,  # Mock long
                            radius_meters=500
                        )
                        db.add(geofence)
                        db.flush()

                        # Create Placement
                        supervisor_contact = f"{placement_data.get('supervisor_name', '')} ({placement_data.get('supervisor_email', '')})"
                        
                        placement = IndustrialPlacement(
                            company_name=placement_data["company_name"],
                            address=placement_data["company_address"],
                            supervisor_contact=supervisor_contact,
                            geofence_id=geofence.id
                        )
                        db.add(placement)
                        db.flush() # Get ID
                        
                        # Link placement to student profile
                        profile.placement_id = placement.id
                        profile.assigned_supervisor_id = supervisor.id
                        
                        # Update dates on profile if needed (already set in profile creation but just in case)
                        # profile.siwes_start_date = ... 

                        print(f"    Added placement at {placement.company_name} (Supervisor: {supervisor.full_name})")
                    else:
                        print(f"    WARNING: Supervisor {supervisor_email} not found for student {student.email}")
            else:
                student = existing_student
                print(f"  Student already exists: {student.full_name}")

            # ENSURE PROFILE EXISTS
            profile = db.query(StudentProfile).filter(StudentProfile.user_id == student.id).first()
            if not profile:
                 profile = StudentProfile(
                    user_id=student.id,
                    matriculation_number=stud_data["matric_number"],
                    department=stud_data["department"],
                    institution="University of Lagos",
                    siwes_start_date=datetime(2024, 3, 1).date(),
                    siwes_end_date=datetime(2024, 8, 31).date()
                )
                 db.add(profile)
                 db.flush()
            
            # ALWAYS Link Supervisor & Placement (Update if needed)
            placement_data = stud_data.get("placement")
            if placement_data:
                supervisor_email = stud_data.get("supervisor_email")
                supervisor = supervisor_map.get(supervisor_email)
                
                if supervisor:
                     # Check/Update Link
                     if profile.assigned_supervisor_id != supervisor.id:
                         profile.assigned_supervisor_id = supervisor.id
                         db.add(profile)
                         db.commit()
                         print(f"    Updated assigned supervisor to: {supervisor.full_name}")
                else:
                    print(f"    WARNING: Supervisor {supervisor_email} not found")

        db.commit()
        print("Data seeding completed successfully!")
        
    except Exception as e:
        print(f"Error seeding data: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    seed_data()
