"""Video call provider service (Daily + Jitsi fallback)."""

import httpx
import json
from typing import Dict, Optional
from datetime import datetime, timedelta
import os
from urllib.parse import quote
from dotenv import load_dotenv

load_dotenv()


class DailyService:
    """Service for managing call rooms using configurable providers.

    Provider selection:
    - VIDEO_PROVIDER=daily  (uses Daily.co)
    - VIDEO_PROVIDER=jitsi  (uses Jitsi room URLs)

    If Daily is selected but credentials are missing, this service falls back
    to Jitsi automatically for local/testing workflows.
    """
    
    def __init__(self):
        """Initialize provider configuration and credentials."""
        requested_provider = (os.getenv("VIDEO_PROVIDER", "jitsi") or "jitsi").lower().strip()
        self.provider = requested_provider if requested_provider in {"daily", "jitsi"} else "daily"

        self.api_key = os.getenv("DAILY_API_KEY")
        self.domain = os.getenv("DAILY_DOMAIN")
        self.base_url = "https://api.daily.co/v1"
        self.jitsi_domain = (os.getenv("JITSI_DOMAIN", "meet.jit.si") or "meet.jit.si").strip()

        if self.provider == "daily" and (not self.api_key or not self.domain):
            # Safe default: allow testing without paid Daily account.
            self.provider = "jitsi"
    
    def create_room(
        self,
        student_id: str,
        supervisor_id: str,
        duration_minutes: int = 60,
        call_type: str = "video",
    ) -> Dict:
        """Create a call room using the configured provider."""
        # Generate unique room name
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        room_name = f"siwes-{student_id[:8]}-{supervisor_id[:8]}-{timestamp}"
        if self.provider == "jitsi":
            return {
                "name": room_name,
                "url": self._get_jitsi_url(room_name, call_type=call_type),
                "created_at": datetime.utcnow().isoformat(),
                "provider": "jitsi",
                "config": {"call_type": call_type},
            }

        # Calculate expiration time
        expires_at = datetime.now() + timedelta(minutes=duration_minutes)
        
        # Primary room configuration. Keep this conservative to avoid
        # Daily account-plan dependent validation failures.
        room_properties = {
            "exp": int(expires_at.timestamp()),  # Unix timestamp
            "max_participants": 2,  # Student + Supervisor only
            "eject_at_room_exp": True,  # Auto-eject when expired
        }
        if call_type == "video":
            room_properties["enable_screenshare"] = True
            room_properties["enable_chat"] = True

        room_config = {
            "name": room_name,
            "privacy": "private",  # Only people with link can join
            "properties": room_properties,
        }

        # Minimal fallback config if strict config is rejected.
        fallback_config = {
            "name": room_name,
            "privacy": "private",
            "properties": {
                "exp": int(expires_at.timestamp()),
                "max_participants": 2,
            },
        }

        # Make Daily API request
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        with httpx.Client() as client:
            response = client.post(
                f"{self.base_url}/rooms",
                json=room_config,
                headers=headers,
                timeout=10.0
            )

            if response.is_success:
                return response.json()

            # Retry once with minimal payload for Daily plan/feature compatibility.
            if response.status_code == 400:
                fallback = client.post(
                    f"{self.base_url}/rooms",
                    json=fallback_config,
                    headers=headers,
                    timeout=10.0
                )
                if fallback.is_success:
                    return fallback.json()
                raise ValueError(self._format_daily_error(fallback))

            raise ValueError(self._format_daily_error(response))

    def _format_daily_error(self, response: httpx.Response) -> str:
        """Build readable error details from Daily API response."""
        body_text = ""
        try:
            data = response.json()
            body_text = json.dumps(data)
        except Exception:
            body_text = (response.text or "").strip()
        if len(body_text) > 600:
            body_text = body_text[:600] + "..."
        return f"Daily API error {response.status_code}: {body_text}"
    
    def get_room(self, room_name: str) -> Optional[Dict]:
        """Get details of an existing room."""
        if self.provider == "jitsi":
            return {
                "name": room_name,
                "url": self.get_room_url(room_name),
                "provider": "jitsi",
            }

        headers = {
            "Authorization": f"Bearer {self.api_key}"
        }
        
        try:
            with httpx.Client() as client:
                response = client.get(
                    f"{self.base_url}/rooms/{room_name}",
                    headers=headers,
                    timeout=10.0
                )
                response.raise_for_status()
                return response.json()
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return None
            raise
    
    def delete_room(self, room_name: str) -> bool:
        """Delete a video call room."""
        if self.provider == "jitsi":
            # Jitsi rooms are ephemeral; nothing to delete server-side.
            return True

        headers = {
            "Authorization": f"Bearer {self.api_key}"
        }
        
        try:
            with httpx.Client() as client:
                response = client.delete(
                    f"{self.base_url}/rooms/{room_name}",
                    headers=headers,
                    timeout=10.0
                )
                response.raise_for_status()
                return True
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return False
            raise
    
    def get_room_url(self, room_name: str) -> str:
        """Get the full URL for joining a room."""
        safe_room = quote(room_name, safe="-_")
        if self.provider == "jitsi":
            return self._get_jitsi_url(room_name, call_type="video")
        return f"https://{self.domain}/{safe_room}"

    def _get_jitsi_url(self, room_name: str, call_type: str = "video") -> str:
        """Build a Jitsi room URL with basic UI config hints."""
        safe_room = quote(room_name, safe="-_")
        is_voice = (call_type or "").lower() == "voice"
        return (
            f"https://{self.jitsi_domain}/{safe_room}"
            "#config.prejoinPageEnabled=false"
            "&config.startWithAudioMuted=false"
            f"&config.startWithVideoMuted={'true' if is_voice else 'false'}"
        )
    
    def create_meeting_token(
        self,
        room_name: str,
        user_name: str,
        is_owner: bool = False
    ) -> str:
        """Create a meeting token for secure room access.

        For Jitsi provider this returns an empty string because no token is
        required in the basic public deployment mode.
        """
        if self.provider == "jitsi":
            return ""

        token_config = {
            "properties": {
                "room_name": room_name,
                "user_name": user_name,
                "is_owner": is_owner,
                "enable_screenshare": True,
                "enable_recording": is_owner,  # Only owner can record
            }
        }
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        with httpx.Client() as client:
            response = client.post(
                f"{self.base_url}/meeting-tokens",
                json=token_config,
                headers=headers,
                timeout=10.0
            )
            response.raise_for_status()
            return response.json()["token"]
