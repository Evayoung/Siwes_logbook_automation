"""SSE notification routes for real-time push notifications."""

from fasthtml.common import *
from sqlalchemy.orm import Session
import asyncio
import json
from datetime import datetime, timedelta
from sqlalchemy import desc

from app.infrastructure.security.session import require_auth
from app.application.services.notifications import notification_manager
from app.application.services.notification import NotificationService
from app.domain.models.user import User, UserRole, StudentProfile
from app.domain.models.chat import ChatMessage, Notification, NotificationType
from app.domain.models.call import CallLog
from app.infrastructure.database.connection import get_db_session
from app.presentation.routes.calls import _build_join_url_for_user, _extract_initiator_id


def register_notification_routes(app):
    """Register SSE notification routes.
    
    Args:
        app: FastHTML application instance
    """
    
    @app.get("/notifications/stream")
    async def notification_stream(request: Request):
        """SSE endpoint for real-time notifications.
        
        Maintains a persistent connection and pushes events to the client.
        
        Args:
            request: FastHTML request object
            
        Yields:
            SSE formatted event strings
        """
        # Manual authentication check for SSE
        # Access session data directly from request
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
                headers={
                    "Cache-Control": "no-cache",
                    "X-Accel-Buffering": "no",
                    "Connection": "keep-alive"
                }
            )
        queue = asyncio.Queue()
        
        # Register this connection
        notification_manager.add_connection(user_id, queue)
        
        async def event_generator():
            """Generate SSE events from the queue."""
            try:
                # Send initial connection confirmation
                yield f"data: {json.dumps({'type': 'connected', 'user_id': user_id})}\n\n"
                
                # Keep connection alive and send events
                while True:
                    # Wait for events with timeout for keep-alive
                    try:
                        event_data = await asyncio.wait_for(queue.get(), timeout=30.0)
                        yield f"data: {event_data}\n\n"
                    except asyncio.TimeoutError:
                        # Send keep-alive comment
                        yield ": keep-alive\n\n"
                        
            except asyncio.CancelledError:
                # Connection closed by client
                pass
            finally:
                # Clean up connection
                notification_manager.remove_connection(user_id, queue)
        
        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
                "Connection": "keep-alive"
            }
        )

    @app.get("/notifications/inbox")
    @require_auth()
    def notifications_inbox(request: Request, db: Session = None, current_user: User = None):
        """Return unread chat notifications for top-bar bell."""
        if current_user.role == UserRole.STUDENT:
            profile = db.query(StudentProfile).filter(StudentProfile.user_id == current_user.id).first()
            if profile and not bool(getattr(profile, "setting_notifications", True)):
                return JSONResponse({"count": 0, "items": []})
        notif_service = NotificationService(db)
        unread = notif_service.get_user_notifications(current_user.id, unread_only=True, limit=20)
        items = []
        for n in unread:
            items.append(
                {
                    "id": n.id,
                    "title": n.title,
                    "message": n.message,
                    "type": n.type.value if n.type else "system_announcement",
                    "time": n.created_at.isoformat() if n.created_at else "",
                    "action_url": n.action_url or "#",
                }
            )

        return JSONResponse({"count": len(items), "items": items})

    @app.post("/notifications/mark-all-read")
    @require_auth()
    def mark_all_read(request: Request, db: Session = None, current_user: User = None):
        """Mark all unread incoming chat messages as read for current user."""
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

    @app.get("/notifications/poll")
    @require_auth()
    def notifications_poll(request: Request, db: Session = None, current_user: User = None):
        """DB-backed notification polling for broker-free deployments.

        This replaces browser dependence on long-lived SSE connections. It is
        intentionally read-only; the bell/inbox keeps ownership of read state.
        """
        events = []

        recent_cutoff = datetime.utcnow() - timedelta(minutes=30)
        call_logs = db.query(CallLog).filter(
            (CallLog.student_id == current_user.id) | (CallLog.supervisor_id == current_user.id),
            CallLog.started_at >= recent_cutoff,
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
