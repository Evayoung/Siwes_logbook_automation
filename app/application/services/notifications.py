"""SSE notification system for real-time call notifications.

This module provides Server-Sent Events (SSE) infrastructure for pushing
real-time notifications to connected clients.
"""

from fasthtml.common import *
from typing import Dict, Set
import asyncio
from datetime import datetime
import json


class NotificationManager:
    """Manages SSE connections for real-time notifications.
    
    Tracks active user connections and provides methods to send
    notifications to specific users.
    """
    
    def __init__(self):
        """Initialize the notification manager."""
        # Maps user_id -> set of queue objects for that user
        self._connections: Dict[str, Set[asyncio.Queue]] = {}
    
    def add_connection(self, user_id: str, queue: asyncio.Queue):
        """Add a new SSE connection for a user.
        
        Args:
            user_id: ID of the user
            queue: Async queue for sending events
        """
        if user_id not in self._connections:
            self._connections[user_id] = set()
        self._connections[user_id].add(queue)
        print(f"[SSE] User {user_id} connected. Total connections: {len(self._connections[user_id])}")
    
    def remove_connection(self, user_id: str, queue: asyncio.Queue):
        """Remove an SSE connection for a user.
        
        Args:
            user_id: ID of the user
            queue: Async queue to remove
        """
        if user_id in self._connections:
            self._connections[user_id].discard(queue)
            if not self._connections[user_id]:
                del self._connections[user_id]
            print(f"[SSE] User {user_id} disconnected")
    
    async def send_to_user(self, user_id: str, event_type: str, data: dict):
        """Send a notification to all connections for a specific user.
        
        Args:
            user_id: ID of the recipient user
            event_type: Type of event (e.g., 'call_incoming')
            data: Event data dictionary
        """
        if user_id not in self._connections:
            print(f"[SSE] User {user_id} not connected, cannot send {event_type}")
            return
        
        event_data = {
            "type": event_type,
            "timestamp": datetime.utcnow().isoformat(),
            **data
        }
        
        # Send to all active connections for this user
        for queue in self._connections[user_id]:
            try:
                await queue.put(json.dumps(event_data))
            except Exception as e:
                print(f"[SSE] Error sending to user {user_id}: {e}")
    
    def get_active_users(self) -> list:
        """Get list of currently connected user IDs.
        
        Returns:
            List of user IDs with active connections
        """
        return list(self._connections.keys())


# Global notification manager instance
notification_manager = NotificationManager()
