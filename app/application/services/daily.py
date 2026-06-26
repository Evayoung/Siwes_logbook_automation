"""Call provider service using LiveKit."""

import base64
import hashlib
import hmac
import json
import os
import time
from datetime import datetime
from typing import Dict, Optional
from urllib.parse import quote_plus

from dotenv import load_dotenv
from app.config import get_settings

load_dotenv()


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("utf-8").rstrip("=")


class LiveKitService:
    """Call provider service for LiveKit rooms and participant tokens."""

    def __init__(self):
        settings = get_settings()
        self.provider = "livekit"
        self.livekit_url = (
            settings.livekit_url
            or os.getenv("LIVEKIT_URL")
            or os.getenv("livekit_url")
            or ""
        ).strip()
        self.livekit_api_key = (
            settings.livekit_api_key
            or os.getenv("LIVEKIT_API_KEY")
            or os.getenv("livekit_api_key")
            or ""
        ).strip()
        self.livekit_api_secret = (
            settings.livekit_api_secret
            or os.getenv("LIVEKIT_API_SECRET")
            or os.getenv("livekit_api_secret")
            or ""
        ).strip()
        if not self.livekit_url or not self.livekit_api_key or not self.livekit_api_secret:
            raise ValueError("Missing LiveKit credentials. Set LIVEKIT_URL, LIVEKIT_API_KEY, and LIVEKIT_API_SECRET.")

    def create_room(
        self,
        student_id: str,
        supervisor_id: str,
        duration_minutes: int = 60,
        call_type: str = "video",
    ) -> Dict:
        """Create a logical room name (LiveKit room is created lazily on join)."""
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        room_name = f"siwes-{student_id[:8]}-{supervisor_id[:8]}-{timestamp}"
        return {
            "name": room_name,
            "url": self.get_room_url(room_name),
            "created_at": datetime.utcnow().isoformat(),
            "provider": "livekit",
            "config": {"call_type": call_type},
        }

    def get_room(self, room_name: str) -> Optional[Dict]:
        return {
            "name": room_name,
            "url": self.get_room_url(room_name),
            "provider": "livekit",
        }

    def delete_room(self, room_name: str) -> bool:
        # Rooms end automatically when participants leave.
        return True

    def get_room_url(self, room_name: str) -> str:
        return self._get_livekit_meet_url(room_name, "")

    def get_join_url(self, room_name: str, token: str) -> str:
        return self._get_livekit_meet_url(room_name, token)

    def _encode_jwt(self, payload: dict) -> str:
        header = {"alg": "HS256", "typ": "JWT"}
        header_segment = _b64url(json.dumps(header, separators=(",", ":")).encode("utf-8"))
        payload_segment = _b64url(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
        signing_input = f"{header_segment}.{payload_segment}".encode("utf-8")
        signature = hmac.new(
            self.livekit_api_secret.encode("utf-8"),
            signing_input,
            hashlib.sha256,
        ).digest()
        return f"{header_segment}.{payload_segment}.{_b64url(signature)}"

    def create_meeting_token(
        self,
        room_name: str,
        user_name: str,
        is_owner: bool = False,
        identity: Optional[str] = None,
    ) -> str:
        now = int(time.time())
        identity_value = (identity or user_name or "user").strip()
        payload = {
            "iss": self.livekit_api_key,
            "sub": identity_value,
            "name": user_name,
            "nbf": now - 10,
            "exp": now + (2 * 60 * 60),
            "video": {
                "roomJoin": True,
                "room": room_name,
                "canPublish": True,
                "canSubscribe": True,
                "canPublishData": True,
            },
            "metadata": json.dumps({"is_owner": bool(is_owner)}),
        }
        return self._encode_jwt(payload)

    def _get_livekit_meet_url(self, room_name: str, token: str) -> str:
        base = "https://meet.livekit.io"
        url = quote_plus(self.livekit_url)
        token_q = quote_plus(token) if token else ""
        # prejoin=false keeps user inside app flow with no extra login/name step.
        return f"{base}/?url={url}&room={room_name}&token={token_q}&prejoin=false"


DailyService = LiveKitService
