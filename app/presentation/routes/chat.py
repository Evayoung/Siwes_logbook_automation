from fasthtml.common import *
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_, desc
from datetime import datetime
from urllib.parse import unquote, quote
from typing import Optional

from app.infrastructure.security.session import require_auth
from app.domain.models.chat import ChatMessage
from app.domain.models.user import User, UserRole, StudentProfile
from app.application.services.notifications import notification_manager
from app.application.services.notification import NotificationService
from app.domain.models.chat import NotificationType
from app.infrastructure.database.connection import get_db
from faststrap.presets import InfiniteScroll

def register_chat_routes(app):
    """Register chat-related routes."""

    def _message_bubble_html(text: str, time_text: str, is_me: bool, message_id: str | None = None, created_at: str | None = None) -> FT:
        """Render a chat bubble snippet for HTMX append."""
        if is_me:
            align_cls = "justify-content-end"
            bubble_cls = "bg-primary text-white rounded-3 rounded-bottom-right-0"
            stack_align = "align-items-end"
        else:
            align_cls = "justify-content-start"
            bubble_cls = "bg-light text-dark rounded-3 rounded-bottom-left-0"
            stack_align = "align-items-start"

        return Div(
            Div(
                Div(
                    text,
                    cls=f"p-3 {bubble_cls}",
                    style="max-width: 80%; box-shadow: 0 1px 2px rgba(0,0,0,0.05);",
                ),
                Div(time_text, cls="text-muted small mt-1 mx-1", style="font-size: 0.7rem;"),
                cls=f"d-flex flex-column {stack_align}",
            ),
            cls=f"d-flex {align_cls} mb-3",
            id=f"chat-message-{message_id}" if message_id else None,
            data_created_at=created_at if created_at else None,
        )

    def _older_messages_payload(
        db: Session,
        current_user_id: str,
        other_user_id: str,
        before: datetime,
        limit: int = 20,
    ):
        rows_desc = db.query(ChatMessage).filter(
            or_(
                and_(ChatMessage.sender_id == current_user_id, ChatMessage.receiver_id == other_user_id),
                and_(ChatMessage.sender_id == other_user_id, ChatMessage.receiver_id == current_user_id),
            ),
            ChatMessage.created_at < before,
        ).order_by(desc(ChatMessage.created_at)).limit(limit + 1).all()

        has_more = len(rows_desc) > limit
        rows = rows_desc[:limit]
        rows_asc = list(reversed(rows))
        oldest = rows[-1].created_at.isoformat() if rows else None
        return rows_asc, has_more, oldest

    @app.get("/api/chat/history/{other_user_id}")
    @require_auth()
    def get_chat_history(
        request: Request,
        other_user_id: str,
        db: Session = None,
        current_user: Optional[User] = None
    ):
        """Fetch chat history with a specific user."""
        messages = db.query(ChatMessage).filter(
            or_(
                and_(ChatMessage.sender_id == current_user.id, ChatMessage.receiver_id == other_user_id),
                and_(ChatMessage.sender_id == other_user_id, ChatMessage.receiver_id == current_user.id)
            )
        ).order_by(ChatMessage.created_at.asc()).all()
        
        return [
            {
                "id": m.id,
                "text": m.message_body,
                "time": m.created_at.strftime("%I:%M %p"),
                "is_me": m.sender_id == current_user.id,
                "created_at": m.created_at.isoformat()
            }
            for m in messages
        ]

    @app.get("/api/chat/history/{other_user_id}/older")
    @require_auth()
    def get_older_chat_history(
        request: Request,
        other_user_id: str,
        before: str,
        limit: int = 20,
        db: Session = None,
        current_user: Optional[User] = None
    ):
        """Fetch older messages for infinite scroll prepend."""
        try:
            before_dt = datetime.fromisoformat(unquote(before))
        except Exception:
            return Div(id="chat-history-sentinel")

        rows_asc, has_more, oldest = _older_messages_payload(
            db=db,
            current_user_id=current_user.id,
            other_user_id=other_user_id,
            before=before_dt,
            limit=max(5, min(limit, 50)),
        )

        top_loader = None
        if has_more and oldest:
            oldest_q = quote(oldest, safe="")
            top_loader = InfiniteScroll(
                endpoint=f"/api/chat/history/{other_user_id}/older?before={oldest_q}&limit={limit}",
                target="this",
                trigger="intersect once root:#chat-messages-list threshold:0.01",
                hx_swap="outerHTML",
                id="chat-history-sentinel",
                content=Div("Loading older messages...", cls="small text-muted text-center py-1"),
            )
        else:
            top_loader = Div("Start of conversation", id="chat-history-sentinel", cls="small text-muted text-center py-1")

        bubbles = [
            _message_bubble_html(
                text=m.message_body,
                time_text=m.created_at.strftime("%I:%M %p"),
                is_me=m.sender_id == current_user.id,
                message_id=m.id,
                created_at=m.created_at.isoformat(),
            )
            for m in rows_asc
        ]
        return (top_loader, *bubbles)

    @app.route("/api/chat/send", methods=["POST", "OPTIONS"])
    async def send_message_route(request: Request):
        """Send a new chat message."""
        # Handle CORS/OPTIONS
        if request.method == "OPTIONS":
            return Response(status_code=200)

        # Authentication (Manual since we need to handle OPTIONS)
        if not hasattr(request, "session") or "user_id" not in request.session:
            return JSONResponse({"error": "Unauthorized"}, status_code=401)
            
        # Get DB Session
        db = request.state.db if hasattr(request.state, 'db') else None
        created_local_session = False
        if not db:
            from app.infrastructure.database.connection import SessionLocal
            db = SessionLocal()
            created_local_session = True
            
        # Get User
        current_user = db.query(User).filter(User.id == request.session["user_id"]).first()
        if not current_user:
            if created_local_session:
                db.close()
            return JSONResponse({"error": "User not found"}, status_code=404)

        try:
            # Parse Body (Support both JSON and Form)
            import json
            
            content_type = request.headers.get("content-type", "")
            
            if "application/json" in content_type:
                # Async read
                body_bytes = await request.body()
                data = json.loads(body_bytes.decode('utf-8'))
                recipient_id = data.get("recipient_id")
                content = data.get("content")
            else:
                # Form data (HTMX default)
                form = await request.form()
                recipient_id = form.get("recipient_id")
                content = form.get("content")
            
            if not recipient_id or not content:
                print(f"Missing fields. Recipient: {recipient_id}, Content: {content}")
                return JSONResponse({"error": "Missing recipient_id or content"}, status_code=400)

            # Validate recipient and chat relationship.
            recipient = db.query(User).filter(User.id == recipient_id).first()
            if not recipient:
                return JSONResponse({"error": "Recipient not found"}, status_code=404)

            if current_user.role == UserRole.STUDENT:
                student_profile = db.query(StudentProfile).filter(
                    StudentProfile.user_id == current_user.id
                ).first()
                if not student_profile or student_profile.assigned_supervisor_id != recipient_id:
                    return JSONResponse(
                        {"error": "You can only message your assigned supervisor"},
                        status_code=403
                    )
            elif current_user.role == UserRole.SUPERVISOR:
                assigned_student_ids = {
                    p.user_id for p in db.query(StudentProfile).filter(
                        StudentProfile.assigned_supervisor_id == current_user.id
                    ).all()
                }
                if recipient_id not in assigned_student_ids:
                    return JSONResponse(
                        {"error": "You can only message assigned students"},
                        status_code=403
                    )
                
            # Create Message
            msg = ChatMessage(
                sender_id=current_user.id,
                receiver_id=recipient_id,
                message_body=content,
                created_at=datetime.utcnow(),
                is_read=False
            )
            db.add(msg)
            db.commit()
            
            # Send SSE Notification
            try:
                await notification_manager.send_to_user(
                    recipient_id,
                    "new_message",
                    {
                        "id": msg.id,
                        "text": msg.message_body,
                        "sender_id": current_user.id,
                        "time": msg.created_at.strftime("%I:%M %p"),
                        "is_me": False  # Recipient sees it as not 'me'
                    }
                )
            except Exception as e:
                print(f"Failed to send SSE: {e}")

            try:
                notif_service = NotificationService(db)
                if recipient.role == UserRole.STUDENT:
                    action_url = f"/student/communication?tab=chat&peer_id={current_user.id}"
                else:
                    action_url = f"/supervisor/communication?student_id={current_user.id}&tab=chat&peer_id={current_user.id}"
                notif_service.create_notification(
                    user_id=recipient_id,
                    notification_type=NotificationType.MESSAGE_RECEIVED,
                    title=f"Message from {current_user.full_name}",
                    message=msg.message_body[:200],
                    action_url=action_url,
                )
                db.commit()
            except Exception:
                db.rollback()

            if request.headers.get("HX-Request"):
                return _message_bubble_html(
                    text=msg.message_body,
                    time_text=msg.created_at.strftime("%I:%M %p"),
                    is_me=True,
                    message_id=msg.id,
                    created_at=msg.created_at.isoformat(),
                )

            return JSONResponse({
                "success": True, 
                "message": {
                    "id": msg.id,
                    "text": msg.message_body,
                    "time": msg.created_at.strftime("%I:%M %p"),
                    "is_me": True
                }
            })
            
        except Exception as e:
            print(f"Error sending message: {e}")
            import traceback
            traceback.print_exc()
            return JSONResponse({"error": str(e)}, status_code=500)
        finally:
            if created_local_session:
                db.close()
