"""Notification manager — supports both SSE queues and WebSocket connections."""

from typing import Dict, Set, Any
import asyncio
import json
from datetime import datetime


class NotificationManager:
    """Manages real-time connections (SSE queues + WebSockets) per user."""

    def __init__(self):
        # SSE: user_id -> set of asyncio.Queue
        self._sse: Dict[str, Set[asyncio.Queue]] = {}
        # WebSocket: user_id -> set of WebSocket objects
        self._ws: Dict[str, Set[Any]] = {}

    # ------------------------------------------------------------------
    # SSE helpers (kept for backward-compat / fallback)
    # ------------------------------------------------------------------

    def add_connection(self, user_id: str, queue: asyncio.Queue):
        self._sse.setdefault(user_id, set()).add(queue)
        print(f"[SSE] {user_id} connected ({len(self._sse[user_id])} tabs)")

    def remove_connection(self, user_id: str, queue: asyncio.Queue):
        if user_id in self._sse:
            self._sse[user_id].discard(queue)
            if not self._sse[user_id]:
                del self._sse[user_id]
        print(f"[SSE] {user_id} disconnected")

    # ------------------------------------------------------------------
    # WebSocket helpers
    # ------------------------------------------------------------------

    def add_ws_connection(self, user_id: str, ws):
        self._ws.setdefault(user_id, set()).add(ws)
        print(f"[WS] {user_id} connected ({len(self._ws[user_id])} tabs)")

    def remove_ws_connection(self, user_id: str, ws):
        if user_id in self._ws:
            self._ws[user_id].discard(ws)
            if not self._ws[user_id]:
                del self._ws[user_id]
        print(f"[WS] {user_id} disconnected")

    # ------------------------------------------------------------------
    # Send helpers
    # ------------------------------------------------------------------

    async def send_to_user(self, user_id: str, event_type: str, data: dict):
        """Push an event to all active connections (WS + SSE) for a user."""
        payload = json.dumps({
            "type": event_type,
            "timestamp": datetime.utcnow().isoformat(),
            **data,
        })

        # WebSocket — preferred path
        dead_ws = set()
        for ws in list(self._ws.get(user_id, set())):
            try:
                await ws.send_text(payload)
            except Exception as e:
                print(f"[WS] dead connection for {user_id}: {e}")
                dead_ws.add(ws)
        for ws in dead_ws:
            self.remove_ws_connection(user_id, ws)

        # SSE — fallback
        for queue in list(self._sse.get(user_id, set())):
            try:
                await queue.put(payload)
            except Exception as e:
                print(f"[SSE] error for {user_id}: {e}")

    def get_active_users(self) -> list:
        """Return user IDs with at least one active WS or SSE connection."""
        return list(set(list(self._ws.keys()) + list(self._sse.keys())))


# Singleton
notification_manager = NotificationManager()
