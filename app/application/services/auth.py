"""Authentication service for user management.

This module provides authentication services including user registration,
login, logout, and profile management.

Example:
    >>> from app.application.services.auth import AuthService
    >>> from app.infrastructure.database import get_db
    >>> 
    >>> with get_db() as db:
    ...     service = AuthService(db)
    ...     user = service.register_student(
    ...         email="student@university.edu",
    ...         password="secure_password",
    ...         full_name="John Doe",
    ...         matric_number="CSC/2020/001",
    ...         department="Computer Science",
    ...         level=400
    ...     )
"""

from typing import Optional, Dict, Any
from datetime import date, datetime, timedelta
from sqlalchemy.orm import Session

from app.domain.models.user import User, UserRole
from app.infrastructure.repositories.user import UserRepository
from app.infrastructure.security.password import hash_password, verify_password, needs_rehash
from app.infrastructure.security.session import create_session


class AuthService:
    """Service for authentication and user management.
    
    Provides methods for user registration, login, password management,
    and profile updates.
    
    Attributes:
        db: Database session for queries
        user_repo: User repository for data access
    
    Example:
        >>> service = AuthService(db)
        >>> user = service.login("student@university.edu", "password123")
    """
    
    def __init__(self, db: Session):
        """Initialize the authentication service.
        
        Args:
            db: Database session for queries
        """
        self.db = db
        self.user_repo = UserRepository(db)
    
    def register_student(
        self,
        email: str,
        password: str,
        full_name: str,
        matriculation_number: str,
        department: str,
        institution: str = "University of Lagos",
        siwes_start_date: Optional[date] = None,
        siwes_end_date: Optional[date] = None,
        phone_number: Optional[str] = None
    ) -> User:
        """Register a new student user.
        
        Args:
            email: Student's email address
            password: Plain text password (will be hashed)
            full_name: Student's full name
            matriculation_number: Student's matriculation number
            department: Student's department
            institution: Student's institution
            siwes_start_date: SIWES start date
            siwes_end_date: SIWES end date
            phone_number: Optional phone number
        
        Returns:
            The created User instance with student profile
        
        Raises:
            ValueError: If email already exists or validation fails
        
        Example:
            >>> user = service.register_student(
            ...     email="student@university.edu",
            ...     password="secure_password",
            ...     full_name="John Doe",
            ...     matriculation_number="CSC/2020/001",
            ...     department="Computer Science",
            ...     institution="University of Lagos"
            ... )
        """
        # Check if email already exists
        if self.user_repo.exists({"email": email}):
            raise ValueError(f"Email {email} is already registered")
        
        # Validate email format
        if "@" not in email:
            raise ValueError("Invalid email format")
        
        # Hash password
        password_hash = hash_password(password)
        
        # Prepare user data
        user_data = {
            "email": email,
            "password_hash": password_hash,
            "full_name": full_name,
            "role": UserRole.STUDENT,
        }
        
        # Prepare student profile data
        profile_data = {
            "matriculation_number": matriculation_number,
            "department": department,
            "institution": institution,
            "siwes_start_date": siwes_start_date or date.today(),
            "siwes_end_date": siwes_end_date or (date.today() + timedelta(weeks=25)),
        }
        
        # Create user with profile
        user = self.user_repo.create_student(user_data, profile_data)
        
        return user
    
    def register_supervisor(
        self,
        email: str,
        password: str,
        full_name: str,
        faculty: str,
        staff_id: str,
        phone_number: Optional[str] = None
    ) -> User:
        """Register a new supervisor user.
        
        Args:
            email: Supervisor's email address
            password: Plain text password (will be hashed)
            full_name: Supervisor's full name
            faculty: Supervisor's faculty
            staff_id: Supervisor's staff ID
            phone_number: Optional phone number
        
        Returns:
            The created User instance with supervisor profile
        
        Raises:
            ValueError: If email already exists or validation fails
        
        Example:
            >>> user = service.register_supervisor(
            ...     email="supervisor@university.edu",
            ...     password="secure_password",
            ...     full_name="Dr. Jane Smith",
            ...     faculty="Faculty of Science",
            ...     staff_id="STAFF001"
            ... )
        """
        # Check if email already exists
        if self.user_repo.exists({"email": email}):
            raise ValueError(f"Email {email} is already registered")
        
        # Validate email format
        if "@" not in email:
            raise ValueError("Invalid email format")
        
        # Hash password
        password_hash = hash_password(password)
        
        # Prepare user data
        user_data = {
            "email": email,
            "password_hash": password_hash,
            "full_name": full_name,
            "role": UserRole.SUPERVISOR,
        }
        
        # Prepare supervisor profile data
        profile_data = {
            "faculty": faculty,
            "staff_id": staff_id
        }
        
        # Create user with profile
        user = self.user_repo.create_supervisor(user_data, profile_data)
        
        return user
    
    def login(self, email: str, password: str) -> Dict[str, Any]:
        """Authenticate a user and create a session.
        
        Args:
            email: User's email address
            password: Plain text password
        
        Returns:
            Dictionary containing:
                - user: The authenticated User instance
                - session: Session data dictionary
                - needs_rehash: Whether password should be rehashed
        
        Raises:
            ValueError: If credentials are invalid
        
        Example:
            >>> result = service.login("student@university.edu", "password123")
            >>> user = result['user']
            >>> session_data = result['session']
        """
        # Get user by email
        user = self.user_repo.get_by_email(email)
        
        if not user:
            raise ValueError("Invalid email or password")
        
        # Verify password
        if not verify_password(password, user.password_hash):
            raise ValueError("Invalid email or password")
        
        # Check if password needs rehashing
        should_rehash = needs_rehash(user.password_hash)
        
        if should_rehash:
            # Rehash with current work factor
            new_hash = hash_password(password)
            self.user_repo.update(user.id, {"password_hash": new_hash})

        self.user_repo.update(user.id, {"last_login_at": datetime.utcnow()})
        
        # Create session
        session_data = create_session(user)
        
        return {
            "user": user,
            "session": session_data,
            "needs_rehash": should_rehash
        }
    
    def change_password(
        self,
        user_id: str,
        old_password: str,
        new_password: str
    ) -> bool:
        """Change a user's password.
        
        Args:
            user_id: User's unique identifier
            old_password: Current password
            new_password: New password
        
        Returns:
            True if password was changed successfully
        
        Raises:
            ValueError: If old password is incorrect or user not found
        
        Example:
            >>> service.change_password(
            ...     user_id=user.id,
            ...     old_password="old_password",
            ...     new_password="new_secure_password"
            ... )
        """
        # Get user
        user = self.user_repo.get_by_id(user_id)
        
        if not user:
            raise ValueError("User not found")
        
        # Verify old password
        if not verify_password(old_password, user.password_hash):
            raise ValueError("Incorrect current password")
        
        # Hash new password
        new_hash = hash_password(new_password)
        
        # Update password
        self.user_repo.update(user_id, {"password_hash": new_hash})
        
        return True
    
    def get_user_with_profile(self, user_id: str) -> Optional[User]:
        """Get a user with their profile loaded.
        
        Args:
            user_id: User's unique identifier
        
        Returns:
            User instance with profile, or None if not found
        
        Example:
            >>> user = service.get_user_with_profile(user_id)
            >>> if user.role == UserRole.STUDENT:
            ...     print(user.student_profile.matriculation_number)
        """
        return self.user_repo.get_user_with_profile(user_id)
    
    def update_profile(
        self,
        user_id: str,
        profile_data: Dict[str, Any]
    ) -> User:
        """Update a user's profile information.
        
        Args:
            user_id: User's unique identifier
            profile_data: Dictionary of profile fields to update
        
        Returns:
            Updated User instance
        
        Raises:
            ValueError: If user not found
        
        Example:
            >>> user = service.update_profile(
            ...     user_id=user.id,
            ...     profile_data={"phone_number": "+234-123-4567"}
            ... )
        """
        # Get user
        user = self.user_repo.get_by_id(user_id)
        
        if not user:
            raise ValueError("User not found")
        
        # Update user fields
        user_fields = {}
        if "full_name" in profile_data:
            user_fields["full_name"] = profile_data.pop("full_name")
        if "phone_number" in profile_data:
            profile_data.pop("phone_number")
        
        if user_fields:
            self.user_repo.update(user_id, user_fields)
        
        # Update profile fields
        if profile_data:
            if user.role == UserRole.STUDENT:
                profile = self.user_repo.get_student_profile(user_id)
                if profile:
                    for key, value in profile_data.items():
                        if hasattr(profile, key):
                            setattr(profile, key, value)
            elif user.role == UserRole.SUPERVISOR:
                profile = self.user_repo.get_supervisor_profile(user_id)
                if profile:
                    for key, value in profile_data.items():
                        if hasattr(profile, key):
                            setattr(profile, key, value)
            
            self.db.flush()
        
        # Refresh and return
        self.db.refresh(user)
        return user
