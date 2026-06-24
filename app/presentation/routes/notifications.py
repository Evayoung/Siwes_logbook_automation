"""Notification routes — WebSocket (primary) + SSE + poll (fallbacks)."""

from fasthtml.common import *
from sqlalchemy.orm import Session
import asyncio
import json
from datetime import datetime, timedelta
from sqlalchemy import desc, or_
from starlette.websockets import WebSocket, WebSocketDisconnect, WebSocketState
from starlette.routing import WebSocketRoute

from app.infrastructure.security.session import require_auth
from app.application.services.notifications import notification_manager
from app.application.services.notification import NotificationService
from app.domain.models.user import User, UserRole, StudentProfile
from app.domain.models.chat import ChatMessage, Notification, NotificationType
from app.domain.models.call import CallLog
from app.infrastructure.database.connection import get_db_session
from app.presentation.routes.calls import _build_join_url_for_user, _extract_initiator_id


# ---------------------------------------------------------------------------
# WebSocket session-cookie parser (fallback when scope session is empty)
# ---------------------------------------------------------------------------

def _user_id_from_ws_cookie(websocket: WebSocket) -> str | None:
    """Extract user_id by re-parsing the signed session cookie.

    Starlette's SessionMiddleware *should* populate scope['session'] for
    WebSocket connections, but in some deployment configurations (reverse
    proxies, ASGI servers) the session dict can be empty even though the
    cookie is present.  This helper unsigns the cookie directly as a
    safety net so the WebSocket never silently drops authenticated users.
    """
    try:
        from itsdangerous import URLSafeTimedSerializer
        from app.config import get_settings
        settings = get_settings()
        serializer = URLSafeTimedSerializer(settings.secret_key, salt="starlette.session")
        cookies = websocket.cookies
        cookie_val = cookies.get("siwes_session")
        if not cookie_val:
            return None
        data = serializer.loads(cookie_val)
        if isinstance(data, dict):
            uid = data.get("user_id")
            if uid:
                # Check expiry
                exp = data.get("expires_at")
                if exp:
                    try:
                        if datetime.fromisoformat(exp) < datetime.utcnow():
                            return None
                    except (ValueError, TypeError):
                        pass
                return uid
    except Exception as exc:
        print(f"[WS] cookie-parse fallback failed: {exc}")
    return None


# ---------------------------------------------------------------------------
# WebSocket handler (standalone — registered separately on the Starlette router)
# ---------------------------------------------------------------------------

async def ws_notifications_handler(websocket: WebSocket):
    """WebSocket endpoint for real-time notifications.

    Replaces the /notifications/poll HTTP-polling mechanism.
    One persistent connection per browser tab — zero DB queries while idle.
    Server pushes events via notification_manager.send_to_user().

    Auth: reads user_id from the signed Starlette session cookie.
    """
    # Authenticate via session cookie — primary path
    session = getattr(websocket, "session", None)
    user_id = session.get("user_id") if session else None

    # Fallback: manually unsign the cookie if scope session is empty
    if not user_id:
        user_id = _user_id_from_ws_cookie(websocket)
        if user_id:
            print(f"[WS] auth via cookie-parse fallback for user {user_id}")

    if not user_id:
        print("[WS] /ws/notifications rejected — no session")
        await websocket.close(code=4001)
        return

    await websocket.accept()
    notification_manager.add_ws_connection(user_id, websocket)
    print(f"[WS] /ws/notifications accepted for user {user_id}")

    try:
        # Send a welcome frame so the client knows the WS is live
        await websocket.send_text(json.dumps({"type": "connected", "user_id": user_id}))

        while True:
            # Wait for a client frame (ping/pong keepalive) with a 25-second timeout.
            # If no client frame arrives in 25 s we send a server ping.
            try:
                msg = await asyncio.wait_for(websocket.receive_text(), timeout=25.0)
                if msg == "ping":
                    await websocket.send_text("pong")
            except asyncio.TimeoutError:
                # Server-initiated ping
                if websocket.client_state == WebSocketState.CONNECTED:
                    await websocket.send_text("ping")

    except WebSocketDisconnect:
        pass
    except Exception as exc:
        print(f"[WS] unexpected error for {user_id}: {exc}")
    finally:
        notification_manager.remove_ws_connection(user_id, websocket)


# ---------------------------------------------------------------------------
# HTTP routes (SSE stream + poll fallback + inbox/mark-read)
# ---------------------------------------------------------------------------

def register_notification_routes(app):
    """Register all notification routes and mount the WebSocket handler."""

    # Mount WebSocket route on the Starlette router
    app.router.routes.insert(0, WebSocketRoute("/ws/notifications", ws_notifications_handler))

    # ------------------------------------------------------------------
    # SSE stream (kept as fallback for clients that can't use WS)
    # ------------------------------------------------------------------

    @app.get("/notifications/stream")
    async def notification_stream(request: Request):
        """SSE fallback endpoint.  Prefer /ws/notifications for new clients."""
        if not hasattr(request, "session") or "user_id" not in request.session:
            return Response(status_code=204)

        user_id = request.session["user_id"]
        if not _notifications_enabled_for_user(user_id):
            async def disabled_generator():
                while True:
                    yield ": notifications-disabled\n\n"
                    await asyncio.sleep(30)
            return StreamingResponse(
                disabled_generator(),
                media_type="text/event-stream",
                headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no", "Connection": "keep-alive"},
            )

        queue = asyncio.Queue()
        notification_manager.add_connection(user_id, queue)

        async def event_generator():
            try:
                yield f"data: {json.dumps({'type': 'connected', 'user_id': user_id})}\n\n"
                while True:
                    try:
                        event_data = await asyncio.wait_for(queue.get(), timeout=30.0)
                        yield f"data: {event_data}\n\n"
                    except asyncio.TimeoutError:
                        yield ": keep-alive\n\n"
            except asyncio.CancelledError:
                pass
            finally:
                notification_manager.remove_connection(user_id, queue)

        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no", "Connection": "keep-alive"},
        )

    # ------------------------------------------------------------------
    # Inbox (bell count)
    # ------------------------------------------------------------------

    @app.get("/notifications/inbox")
    @require_auth()
    def notifications_inbox(request: Request, db: Session = None, current_user: User = None):
        """Return unread notifications for the top-bar bell."""
        try:
            if current_user.role == UserRole.STUDENT:
                profile = db.query(StudentProfile).filter(StudentProfile.user_id == current_user.id).first()
                if profile and not bool(getattr(profile, "setting_notifications", True)):
                    return JSONResponse({"count": 0, "items": []})
            notif_service = NotificationService(db)
            unread = notif_service.get_user_notifications(current_user.id, unread_only=True, limit=20)
            items = [
                {
                    "id": n.id,
                    "title": n.title,
                    "message": n.message,
                    "type": n.type.value if n.type else "system_announcement",
                    "time": n.created_at.isoformat() if n.created_at else "",
                    "action_url": n.action_url or "#",
                }
                for n in unread
            ]
            return JSONResponse({"count": len(items), "items": items})
        except Exception as exc:
            print(f"[INBOX] error: {exc}")
            return JSONResponse({"count": 0, "items": []})

    # ------------------------------------------------------------------
    # Mark all read
    # ------------------------------------------------------------------

    @app.post("/notifications/mark-all-read")
    @require_auth()
    def mark_all_read(request: Request, db: Session = None, current_user: User = None):
        """Mark all unread notifications as read for the current user."""
        try:
            if current_user.role == UserRole.STUDENT:
                profile = db.query(StudentProfile).filter(StudentProfile.user_id == current_user.id).first()
                if profile and not bool(getattr(profile, "setting_notifications", True)):
                    return JSONResponse({"updated": 0})
            updated = db.query(Notification).filter(
                Notification.user_id == current_user.id,
                Notification.is_read == False,
            ).update({"is_read": True}, synchronize_session=False)
            db.commit()
            return JSONResponse({"updated": updated})
        except Exception as exc:
            print(f"[MARK-READ] error: {exc}")
            try:
                db.rollback()
            except Exception:
                pass
            return JSONResponse({"updated": 0})

    # ------------------------------------------------------------------
    # Poll fallback (called at a much longer interval now — 30 s)
    # ------------------------------------------------------------------

    @app.get("/notifications/poll")
    @require_auth()
    def notifications_poll(request: Request, db: Session = None, current_user: User = None):
        """HTTP-polling fallback.  Clients with an active WS skip this.

        Intentionally read-only. Returns empty events on any DB error so a
        transient Supabase error never crashes the ASGI app with a 500.
        """
        try:
            events = []

            recent_cutoff = datetime.utcnow() - timedelta(minutes=30)
            call_logs = db.query(CallLog).filter(
                (CallLog.student_id == current_user.id) | (CallLog.supervisor_id == current_user.id),
                # Ringing calls have started_at=NULL (set only when call becomes active).
                # Include them so incoming-call notifications are never missed.
                or_(
                    CallLog.started_at >= recent_cutoff,
                    CallLog.started_at == None,
                ),
                CallLog.status.in_(["ringing", "accepted", "declined", "missed", "cancelled"]),
            ).order_by(desc(CallLog.started_at)).limit(10).all()

            user_ids = set()
            for call in call_logs:
                user_ids.add(call.student_id)
                user_ids.add(call.supervisor_id)
            users = db.query(User).filter(User.id.in_(user_ids)).all() if user_ids else []
            user_by_id = {u.id: u for u in users}

            for call in call_logs:
                initiator_id = _extract_initiator_id(call.notes)
                current_is_initiator = initiator_id == current_user.id
                other_id = call.supervisor_id if current_user.id == call.student_id else call.student_id
                other_user = user_by_id.get(other_id)

                if call.status == "ringing" and not current_is_initiator:
                    events.append({
                        "event_id": f"call:{call.id}:ringing",
                        "type": "call_incoming",
                        "call_id": call.id,
                        "caller_id": initiator_id or other_id,
                        "caller_name": other_user.full_name if other_user else "Unknown",
                        "call_type": call.call_type or "video",
                        "room_url": call.room_url,
                    })
                elif current_is_initiator and call.status == "accepted":
                    events.append({
                        "event_id": f"call:{call.id}:accepted",
                        "type": "call_accepted",
                        "call_id": call.id,
                        "redirect_url": _build_join_url_for_user(
                            current_user.role,
                            call.room_name,
                            call.call_type or "video",
                        ),
                    })
                elif current_is_initiator and call.status in {"declined", "missed", "cancelled"}:
                    events.append({
                        "event_id": f"call:{call.id}:{call.status}",
                        "type": "call_cancelled",
                        "call_id": call.id,
                        "reason": call.status,
                    })

            unread_messages = db.query(ChatMessage).filter(
                ChatMessage.receiver_id == current_user.id,
                ChatMessage.is_read == False,
            ).order_by(desc(ChatMessage.created_at)).limit(10).all()

            for msg in reversed(unread_messages):
                events.append({
                    "event_id": f"message:{msg.id}",
                    "type": "new_message",
                    "id": msg.id,
                    "text": msg.message_body,
                    "sender_id": msg.sender_id,
                    "time": msg.created_at.strftime("%I:%M %p") if msg.created_at else "",
                    "is_me": False,
                })

            notifications = db.query(Notification).filter(
                Notification.user_id == current_user.id,
                Notification.is_read == False,
            ).order_by(desc(Notification.created_at)).limit(20).all()

            for notif in reversed(notifications):
                notif_type = notif.type
                if notif_type in {NotificationType.LOG_VERIFIED, NotificationType.LOG_FLAGGED, NotificationType.LOG_REVIEWED}:
                    status = "pending"
                    if notif_type == NotificationType.LOG_VERIFIED:
                        status = "verified"
                    elif notif_type == NotificationType.LOG_FLAGGED:
                        status = "flagged"
                    events.append({
                        "event_id": f"notification:{notif.id}",
                        "type": "log_reviewed",
                        "log_id": notif.related_log_id,
                        "status": status,
                        "message": notif.message,
                    })
                elif notif_type == NotificationType.SYSTEM_ANNOUNCEMENT and "submitted" in (notif.message or "").lower():
                    student_name = (notif.message or "A student").split(" submitted", 1)[0]
                    events.append({
                        "event_id": f"notification:{notif.id}",
                        "type": "log_submitted",
                        "student_name": student_name or "A student",
                        "message": notif.message,
                    })

            return JSONResponse({"events": events})

        except Exception as exc:
            print(f"[POLL] ignored transient error: {exc}")
            try:
                db.rollback()
            except Exception:
                pass
            return JSONResponse({"events": []})


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _notifications_enabled_for_user(user_id: str) -> bool:
    db = get_db_session()
    try:
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            return True
        if user.role != UserRole.STUDENT:
            return True
        profile = db.query(StudentProfile).filter(StudentProfile.user_id == user_id).first()
        if not profile:
            return True
        return bool(getattr(profile, "setting_notifications", True))
    except Exception:
        return True
    finally:
        db.close()
