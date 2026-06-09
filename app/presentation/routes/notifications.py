"""SSE notification routes for real-time push notifications."""

from fasthtml.common import *
from sqlalchemy.orm import Session
import asyncio
import json
from sqlalchemy import desc

from app.infrastructure.security.session import require_auth
from app.application.services.notifications import notification_manager
from app.application.services.notification import NotificationService
from app.domain.models.user import User, UserRole, StudentProfile
from app.domain.models.chat import Notification
from app.infrastructure.database.connection import get_db_session


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
