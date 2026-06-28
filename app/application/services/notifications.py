"""Notification manager — supports cross-replica database sync, SSE, and WebSockets."""

from typing import Dict, Set, Any
import asyncio
import json
from datetime import datetime


class NotificationManager:
    """Manages real-time connections (SSE queues + WebSockets) per user with multi-replica sync."""

    def __init__(self):
        # SSE: user_id -> set of asyncio.Queue
        self._sse: Dict[str, Set[asyncio.Queue]] = {}
        # WebSocket: user_id -> set of WebSocket objects
        self._ws: Dict[str, Set[Any]] = {}
        self._cleanup_counter = 0

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
    # Cross-Replica Sync Synchronization Logic
    # ------------------------------------------------------------------

    def start_broadcast_listener(self):
        """Start the background task to poll notification_broadcasts from the database."""
        asyncio.create_task(self._poll_broadcasts_loop())

    async def _poll_broadcasts_loop(self):
        """Poll the notification_broadcasts table for new messages to push to local connections."""
        print("[NOTIFICATION-SYNC] Starting cross-replica broadcast listener loop...")
        
        from app.infrastructure.database.connection import SessionLocal
        from sqlalchemy import text
        
        # Initialize last_seen_id to current max ID to prevent replaying past notifications
        def _get_max_id():
            db = SessionLocal()
            try:
                res = db.execute(text("SELECT MAX(id) FROM notification_broadcasts")).scalar()
                return int(res) if res is not None else 0
            except Exception as e:
                print(f"[NOTIFICATION-SYNC ERROR] Failed to fetch max ID: {e}")
                return 0
            finally:
                db.close()

        loop = asyncio.get_running_loop()
        last_seen_id = await loop.run_in_executor(None, _get_max_id)
        print(f"[NOTIFICATION-SYNC] Initialized last_seen_id to {last_seen_id}")

        def _fetch_new_broadcasts(last_id):
            db = SessionLocal()
            try:
                query = text(
                    "SELECT id, user_id, event_type, data FROM notification_broadcasts "
                    "WHERE id > :last_id ORDER BY id ASC LIMIT 100"
                )
                return db.execute(query, {"last_id": last_id}).all()
            except Exception as e:
                print(f"[NOTIFICATION-SYNC ERROR] Fetch query failed: {e}")
                raise
            finally:
                db.close()

        def _cleanup_old_broadcasts():
            db = SessionLocal()
            try:
                from datetime import datetime, timedelta
                cutoff = datetime.utcnow() - timedelta(hours=1)
                db.execute(
                    text("DELETE FROM notification_broadcasts WHERE created_at < :cutoff"),
                    {"cutoff": cutoff}
                )
                db.commit()
                print("[NOTIFICATION-SYNC] Cleaned up expired notification broadcasts.")
            except Exception as e:
                print(f"[NOTIFICATION-SYNC ERROR] Failed to cleanup table: {e}")
                db.rollback()
            finally:
                db.close()

        consecutive_errors = 0
        cleanup_counter = 0
        
        while True:
            await asyncio.sleep(1.0)  # poll interval: 1 second
            
            try:
                rows = await loop.run_in_executor(None, _fetch_new_broadcasts, last_seen_id)
                consecutive_errors = 0
                
                if rows:
                    for row in rows:
                        broadcast_id, user_id, event_type, data_str = row
                        last_seen_id = max(last_seen_id, broadcast_id)
                        await self._send_to_local_user(user_id, event_type, json.loads(data_str))
                
                cleanup_counter += 1
                if cleanup_counter >= 300:  # approx. every 5 minutes
                    cleanup_counter = 0
                    await loop.run_in_executor(None, _cleanup_old_broadcasts)
                        
            except Exception as e:
                consecutive_errors += 1
                delay = min(30, 2 ** consecutive_errors)
                print(f"[NOTIFICATION-SYNC ERROR] Loop failed: {e}. Retrying in {delay}s...")
                await asyncio.sleep(delay)

    # ------------------------------------------------------------------
    # Send helpers
    # ------------------------------------------------------------------

    async def send_to_user(self, user_id: str, event_type: str, data: dict):
        """Broadcast an event to a user across all replicas by writing to the DB."""
        try:
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(None, self._write_broadcast_sync, user_id, event_type, data)
        except Exception as e:
            print(f"[NOTIFICATION-SYNC ERROR] Failed to broadcast; falling back to local send: {e}")
            # Fallback: send to local connections immediately in case DB is down
            await self._send_to_local_user(user_id, event_type, data)

    def _write_broadcast_sync(self, user_id: str, event_type: str, data: dict):
        """Synchronously write broadcast to DB."""
        from app.infrastructure.database.connection import SessionLocal
        from sqlalchemy import text
        
        db = SessionLocal()
        try:
            query = text(
                "INSERT INTO notification_broadcasts (user_id, event_type, data, created_at) "
                "VALUES (:user_id, :event_type, :data, :created_at)"
            )
            db.execute(query, {
                "user_id": user_id,
                "event_type": event_type,
                "data": json.dumps(data),
                "created_at": datetime.utcnow()
            })
            db.commit()
            print(f"[NOTIFICATION-SYNC] Broadcast registered: user={user_id} type={event_type}")
        except Exception as e:
            print(f"[NOTIFICATION-SYNC ERROR] Failed to write broadcast to DB: {e}")
            db.rollback()
            raise
        finally:
            db.close()

    async def _send_to_local_user(self, user_id: str, event_type: str, data: dict):
        """Push an event ONLY to local active connections on this replica."""
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
                print(f"[WS] dead local connection for {user_id}: {e}")
                dead_ws.add(ws)
        for ws in dead_ws:
            self.remove_ws_connection(user_id, ws)

        # SSE — fallback
        for queue in list(self._sse.get(user_id, set())):
            try:
                await queue.put(payload)
            except Exception as e:
                print(f"[SSE] local error for {user_id}: {e}")

    def get_active_users(self) -> list:
        """Return user IDs with at least one active WS or SSE connection."""
        return list(set(list(self._ws.keys()) + list(self._sse.keys())))


# Singleton
notification_manager = NotificationManager()
