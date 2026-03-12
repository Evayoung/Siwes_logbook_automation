"""Legacy Daily.co API client for video and voice calls.

This module provides a client for interacting with the legacy Daily.co API to create
and manage video call rooms for student-supervisor consultations.

Example:
    >>> from app.infrastructure.services.daily_client import DailyClient
    >>> from app.config import get_settings
    >>> 
    >>> settings = get_settings()
    >>> client = DailyClient(settings.daily_api_key)
    >>> 
    >>> # Create a room
    >>> room = await client.create_room(
    ...     name="student-supervisor-consultation",
    ...     max_participants=2
    ... )
    >>> print(room['url'])
"""

import httpx
from typing import Dict, Any, Optional
from datetime import datetime, timedelta


class DailyClient:
    """Client for legacy Daily.co API operations.
    
    Provides methods to create, manage, and delete video call rooms using
    the Daily.co REST API.
    
    Attributes:
        api_key: Daily.co API key for authentication
        base_url: Base URL for legacy Daily.co API (default: https://api.daily.co/v1)
    
    Example:
        >>> client = DailyClient(api_key="your_api_key")
        >>> room = await client.create_room(name="consultation-123")
    
    Note:
        - Requires a Daily.co account and API key
        - Free tier includes 10,000 minutes/month
        - All methods are async and require await
    """
    
    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.daily.co/v1"
    ):
        """Initialize the legacy Daily.co client.
        
        Args:
            api_key: Daily.co API key
            base_url: Base URL for the API (default: https://api.daily.co/v1)
        """
        self.api_key = api_key
        self.base_url = base_url
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
    
    async def create_room(
        self,
        name: Optional[str] = None,
        privacy: str = "private",
        max_participants: int = 2,
        enable_chat: bool = True,
        enable_screenshare: bool = True,
        start_video_off: bool = False,
        start_audio_off: bool = False,
        exp_minutes: int = 60
    ) -> Dict[str, Any]:
        """Create a new video call room.
        
        Args:
            name: Optional room name (auto-generated if not provided)
            privacy: Room privacy setting ("public" or "private")
            max_participants: Maximum number of participants (default: 2)
            enable_chat: Whether to enable in-call chat
            enable_screenshare: Whether to enable screen sharing
            start_video_off: Whether to start with video off
            start_audio_off: Whether to start with audio off
            exp_minutes: Room expiration time in minutes (default: 60)
        
        Returns:
            Dictionary containing room details including:
                - id: Room ID
                - name: Room name
                - url: Room URL for joining
                - created_at: Creation timestamp
        
        Example:
            >>> room = await client.create_room(
            ...     name="student-123-supervisor-456",
            ...     max_participants=2,
            ...     exp_minutes=30
            ... )
            >>> print(f"Join at: {room['url']}")
        
        Raises:
            httpx.HTTPError: If the API request fails
        
        Note:
            - Private rooms require a meeting token to join
            - Rooms auto-delete after expiration time
            - Free tier has limits on concurrent rooms
        """
        # Calculate expiration time
        exp_time = datetime.utcnow() + timedelta(minutes=exp_minutes)
        
        # Prepare room properties
        properties = {
            "enable_chat": enable_chat,
            "enable_screenshare": enable_screenshare,
            "start_video_off": start_video_off,
            "start_audio_off": start_audio_off,
            "max_participants": max_participants,
            "exp": int(exp_time.timestamp())
        }
        
        # Prepare request payload
        payload: Dict[str, Any] = {
            "privacy": privacy,
            "properties": properties
        }
        
        if name:
            payload["name"] = name
        
        # Make API request
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/rooms",
                headers=self.headers,
                json=payload
            )
            response.raise_for_status()
            return response.json()
    
    async def get_room(self, room_name: str) -> Dict[str, Any]:
        """Get details of an existing room.
        
        Args:
            room_name: The room name or ID
        
        Returns:
            Dictionary containing room details
        
        Example:
            >>> room = await client.get_room("student-123-supervisor-456")
            >>> print(f"Created: {room['created_at']}")
        
        Raises:
            httpx.HTTPError: If the room is not found or API request fails
        """
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/rooms/{room_name}",
                headers=self.headers
            )
            response.raise_for_status()
            return response.json()
    
    async def delete_room(self, room_name: str) -> Dict[str, Any]:
        """Delete a room.
        
        Args:
            room_name: The room name or ID to delete
        
        Returns:
            Dictionary containing deletion confirmation
        
        Example:
            >>> result = await client.delete_room("student-123-supervisor-456")
            >>> print(f"Deleted: {result['deleted']}")
        
        Raises:
            httpx.HTTPError: If the room is not found or API request fails
        
        Note:
            - Deleting a room ends any active calls
            - This action cannot be undone
        """
        async with httpx.AsyncClient() as client:
            response = await client.delete(
                f"{self.base_url}/rooms/{room_name}",
                headers=self.headers
            )
            response.raise_for_status()
            return response.json()
    
    async def create_meeting_token(
        self,
        room_name: str,
        user_name: str,
        is_owner: bool = False,
        enable_recording: bool = False,
        exp_minutes: int = 60
    ) -> str:
        """Create a meeting token for joining a private room.
        
        Args:
            room_name: The room name or ID
            user_name: Display name for the user
            is_owner: Whether the user has owner privileges
            enable_recording: Whether the user can record
            exp_minutes: Token expiration time in minutes
        
        Returns:
            Meeting token string
        
        Example:
            >>> token = await client.create_meeting_token(
            ...     room_name="consultation-123",
            ...     user_name="Dr. Jane Smith",
            ...     is_owner=True
            ... )
            >>> join_url = f"https://yourdomain.daily.co/{room_name}?t={token}"
        
        Raises:
            httpx.HTTPError: If the API request fails
        
        Note:
            - Required for joining private rooms
            - Tokens expire after the specified time
            - Owner can control room settings and end calls
        """
        # Calculate expiration time
        exp_time = datetime.utcnow() + timedelta(minutes=exp_minutes)
        
        # Prepare token properties
        properties = {
            "room_name": room_name,
            "user_name": user_name,
            "is_owner": is_owner,
            "enable_recording": enable_recording,
            "exp": int(exp_time.timestamp())
        }
        
        # Make API request
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/meeting-tokens",
                headers=self.headers,
                json={"properties": properties}
            )
            response.raise_for_status()
            result = response.json()
            return result["token"]
    
    async def list_rooms(
        self,
        limit: int = 10,
        ending_before: Optional[str] = None
    ) -> Dict[str, Any]:
        """List all rooms.
        
        Args:
            limit: Maximum number of rooms to return (default: 10)
            ending_before: Room ID to paginate before
        
        Returns:
            Dictionary containing:
                - total_count: Total number of rooms
                - data: List of room objects
        
        Example:
            >>> rooms = await client.list_rooms(limit=20)
            >>> for room in rooms['data']:
            ...     print(f"{room['name']}: {room['url']}")
        
        Raises:
            httpx.HTTPError: If the API request fails
        """
        params = {"limit": limit}
        if ending_before:
            params["ending_before"] = ending_before
        
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/rooms",
                headers=self.headers,
                params=params
            )
            response.raise_for_status()
            return response.json()

