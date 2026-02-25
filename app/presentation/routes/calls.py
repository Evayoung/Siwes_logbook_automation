"""Video call routes for Daily.co integration.

This module provides routes for creating and joining video calls
between students and supervisors.
"""

from fasthtml.common import *
from sqlalchemy.orm import Session
from datetime import datetime
import asyncio
from typing import Optional

from app.infrastructure.security.session import require_auth, require_role
from app.application.services.daily import DailyService
from faststrap.presets import hx_redirect, hx_trigger
from app.domain.models.call import CallLog
from app.domain.models.user import UserRole, User
from app.application.services.notification import NotificationService
from app.domain.models.chat import NotificationType
from app.application.services.notifications import notification_manager
from app.infrastructure.database.connection import SessionLocal
from app.config import get_settings


def _hx_call_error(message: str):
    """Send a call error event and close incoming-call modal on HTMX clients."""
    return hx_trigger(
        {
            "call_declined": True,
            "call_error": {"message": message},
        }
    )


def _build_join_url_for_user(role: UserRole, room_name: str, call_type: str) -> str:
    """Build call join URL for a participant role."""
    if role == UserRole.STUDENT:
        url = f"/student/call/{room_name}"
    else:
        url = f"/supervisor/call/{room_name}"
    if call_type == "voice":
        url += "?video=false"
    return url


def _caller_and_peer(call_log: CallLog) -> tuple[Optional[str], Optional[str]]:
    """Resolve caller and peer user IDs from call log metadata."""
    initiator_id = _extract_initiator_id(call_log.notes)
    if initiator_id:
        peer_id = call_log.supervisor_id if initiator_id == call_log.student_id else call_log.student_id
        return initiator_id, peer_id
    return None, None


async def _auto_mark_missed_call(call_id: str, timeout_seconds: int = 75):
    """Mark ringing call as missed after timeout and notify caller."""
    await asyncio.sleep(timeout_seconds)
    db = SessionLocal()
    try:
        call_log = db.query(CallLog).filter(CallLog.id == call_id).first()
        if not call_log or call_log.status != "ringing":
            return

        call_log.status = "missed"
        call_log.ended_at = datetime.utcnow()
        db.commit()

        caller_id, peer_id = _caller_and_peer(call_log)
        if not caller_id:
            return

        await notification_manager.send_to_user(
            caller_id,
            "call_cancelled",
            {"call_id": call_id, "reason": "missed"}
        )

        notif_service = NotificationService(db)
        if caller_id == call_log.student_id:
            callback_url = f"/student/communication?tab=calls&peer_id={call_log.supervisor_id}"
        else:
            callback_url = f"/supervisor/communication?tab=calls&student_id={call_log.student_id}&peer_id={call_log.student_id}"

        notif_service.create_notification(
            user_id=caller_id,
            notification_type=NotificationType.SYSTEM_ANNOUNCEMENT,
            title="Missed Call",
            message="Your call was not answered.",
            action_url=callback_url,
        )
        db.commit()
    except Exception as e:
        db.rollback()
        print(f"[CALL ERROR] failed to auto-mark missed call {call_id}: {e}")
    finally:
        db.close()


def register_call_routes(app):
    """Register video call routes.
    
    Args:
        app: FastHTML application instance
    """
    
    @app.route("/api/calls/create", methods=["POST", "OPTIONS"])
    async def create_call_route(request: Request):
        """Handle call creation with manual JSON parsing.
        
        This bypasses FastHTML's automatic parameter injection which
        causes 'Missing required field: func' errors with JSON POST data.
        """
        # Handle CORS preflight
        if request.method == "OPTIONS":
            return Response(
                status_code=200,
                headers={
                    "Access-Control-Allow-Origin": "*",
                    "Access-Control-Allow-Methods": "POST, OPTIONS",
                    "Access-Control-Allow-Headers": "Content-Type",
                }
            )
        
        # Manual auth check
        if not hasattr(request, "session") or "user_id" not in request.session:
            return JSONResponse(
                {"error": "Unauthorized"},
                status_code=401,
                headers={"Content-Type": "application/json"}
            )
        
        # Get current user
        # DB session is injected by DBSessionMiddleware
        db = request.state.db if hasattr(request.state, 'db') else None
        if not db:
            from app.infrastructure.database.connection import SessionLocal
            db = SessionLocal()
        
        from app.domain.models.user import User
        
        current_user = db.query(User).filter(User.id == request.session["user_id"]).first()
        if not current_user:
            return JSONResponse(
                {"error": "User not found"},
                status_code=404,
                headers={"Content-Type": "application/json"}
            )
        
        # Only students and supervisors can initiate calls
        if current_user.role not in [UserRole.STUDENT, UserRole.SUPERVISOR]:
            return JSONResponse(
                {"error": "Unauthorized role"},
                status_code=403,
                headers={"Content-Type": "application/json"}
            )
        
        try:
            # Parse body (support both JSON and HTMX form submissions)
            content_type = request.headers.get("content-type", "")
            if "application/json" in content_type:
                data = await request.json()
            else:
                form = await request.form()
                data = dict(form)
            
            call_type = data.get("call_type", "video")
            supervisor_id = data.get("supervisor_id")
            student_id = data.get("student_id")
            
            print(f"[CALL] Received: call_type={call_type}, supervisor_id={supervisor_id}, student_id={student_id}")
            print(f"[CALL] Current user: {current_user.full_name} ({current_user.role})")
            
            # Determine participants based on role
            if current_user.role == UserRole.STUDENT:
                student_id = current_user.id
                # supervisor_id should come from request
                if not supervisor_id:
                    print(f"[CALL ERROR] Missing supervisor_id")
                    if request.headers.get("HX-Request"):
                        return _hx_call_error("No supervisor selected for this call")
                    return JSONResponse(
                        {"error": "supervisor_id is required"},
                        status_code=400,
                        headers={"Content-Type": "application/json"}
                    )
            else:
                # Supervisor initiating call
                supervisor_id = current_user.id
                # student_id should come from request
                if not student_id:
                    print(f"[CALL ERROR] Missing student_id")
                    if request.headers.get("HX-Request"):
                        return _hx_call_error("No student selected for this call")
                    return JSONResponse(
                        {"error": "student_id is required"},
                        status_code=400,
                        headers={"Content-Type": "application/json"}
                    )

            # Create Daily.co room
            daily_service = DailyService()
            room = daily_service.create_room(
                student_id=student_id,
                supervisor_id=supervisor_id,
                duration_minutes=60,
                call_type=call_type,
            )
            
            # Save to database with 'ringing' status
            call_log = CallLog(
                room_name=room["name"],
                room_url=room["url"],
                student_id=student_id,
                supervisor_id=supervisor_id,
                status="ringing",
                call_type=call_type,
                notified_at=datetime.utcnow(),
                notes=f"initiator:{current_user.id}"
            )
            db.add(call_log)
            db.commit()
            
            # Send SSE notification to recipient
            # Determine recipient
            recipient_id = supervisor_id if current_user.role == UserRole.STUDENT else student_id
            caller = db.query(User).filter(User.id == current_user.id).first()
            
            await notification_manager.send_to_user(
                recipient_id,
                "call_incoming",
                {
                    "call_id": call_log.id,
                    "caller_id": current_user.id,
                    "caller_name": caller.full_name if caller else "Unknown",
                    "call_type": call_type,
                    "room_url": room["url"]
                }
            )

            try:
                notif_service = NotificationService(db)
                if current_user.role == UserRole.STUDENT:
                    action_url = "/supervisor/communication?tab=calls"
                else:
                    action_url = f"/student/communication?tab=calls&peer_id={current_user.id}"
                notif_service.create_notification(
                    user_id=recipient_id,
                    notification_type=NotificationType.CALL_REQUEST,
                    title=f"Incoming {call_type.capitalize()} Call",
                    message=f"{caller.full_name if caller else 'A user'} is calling you.",
                    action_url=action_url,
                )
                db.commit()
            except Exception:
                db.rollback()

            # Auto-mark as missed if nobody responds in time.
            settings = get_settings()
            asyncio.create_task(
                _auto_mark_missed_call(call_log.id, settings.call_ring_timeout_seconds)
            )
            
            # Determine redirect URL based on role
            redirect_url = _build_join_url_for_user(
                current_user.role, room["name"], call_type
            )

            # HTMX clients expect redirect header, not JSON.
            if request.headers.get("HX-Request"):
                return hx_redirect(redirect_url)
            
            return JSONResponse({
                "success": True,
                "room_name": room["name"],
                "room_url": room["url"],
                "call_id": call_log.id,
                "redirect_url": redirect_url
            })
            
        except Exception as e:
            db.rollback()
            import traceback
            print(f"[CALL ERROR] create_call_route failed: {e}")
            traceback.print_exc()
            if request.headers.get("HX-Request"):
                return _hx_call_error(f"Unable to start call: {str(e)}")
            return JSONResponse(
                {"error": str(e)},
                status_code=500
            )
    
    @app.post("/api/calls/{call_id}/accept")
    @require_auth()
    async def accept_call(
        request: Request,
        call_id: str,
        db: Session = None,
        current_user: Optional[User] = None
    ):
        """Accept an incoming call.
        
        Args:
            request: FastHTML request object
            call_id: Call log ID
            db: Database session
            current_user: Authenticated user
        
        Returns:
            JSON response with redirect URL
        """
        # Get call log
        call_log = db.query(CallLog).filter(CallLog.id == call_id).first()
        
        if not call_log:
            if request.headers.get("HX-Request"):
                return _hx_call_error("Call not found")
            return JSONResponse({"error": "Call not found"}, status_code=404)
        
        if call_log.status != "ringing":
            if request.headers.get("HX-Request"):
                return _hx_call_error("Call is no longer available")
            return JSONResponse({"error": "Call is no longer available"}, status_code=409)

        # Verify user is the recipient
        if call_log.student_id != current_user.id and call_log.supervisor_id != current_user.id:
            if request.headers.get("HX-Request"):
                return _hx_call_error("Unauthorized")
            return JSONResponse({"error": "Unauthorized"}, status_code=403)

        initiator_id = _extract_initiator_id(call_log.notes)
        if initiator_id and current_user.id == initiator_id:
            if request.headers.get("HX-Request"):
                return _hx_call_error("Only the recipient can accept this call")
            return JSONResponse({"error": "Only the recipient can accept this call"}, status_code=403)
        
        # Update call status
        call_log.status = "accepted"
        db.commit()
        
        # Determine redirect URL
        redirect_url = _build_join_url_for_user(
            current_user.role, call_log.room_name, call_log.call_type or "video"
        )
        
        # Notify caller that call was accepted
        caller_id = call_log.supervisor_id if current_user.role == UserRole.STUDENT else call_log.student_id
        
        await notification_manager.send_to_user(
            caller_id,
            "call_accepted",
            {
                "call_id": call_id,
                "redirect_url": redirect_url
            }
        )

        try:
            notif_service = NotificationService(db)
            notif_service.create_notification(
                user_id=caller_id,
                notification_type=NotificationType.SYSTEM_ANNOUNCEMENT,
                title="Call Accepted",
                message=f"{current_user.full_name} accepted your call.",
                action_url=redirect_url,
            )
            db.commit()
        except Exception:
            db.rollback()
        
        if request.headers.get("HX-Request"):
            return hx_redirect(redirect_url)

        return JSONResponse({
            "success": True,
            "redirect_url": redirect_url
        })
    
    @app.post("/api/calls/{call_id}/decline")
    @require_auth()
    async def decline_call(
        request: Request,
        call_id: str,
        db: Session = None,
        current_user: Optional[User] = None
    ):
        """Decline an incoming call.
        
        Args:
            request: FastHTML request object
            call_id: Call log ID
            db: Database session
            current_user: Authenticated user
        
        Returns:
            JSON response with success status
        """
        # Get call log
        call_log = db.query(CallLog).filter(CallLog.id == call_id).first()
        
        if not call_log:
            if request.headers.get("HX-Request"):
                return _hx_call_error("Call not found")
            return JSONResponse({"error": "Call not found"}, status_code=404)
        
        if call_log.status != "ringing":
            if request.headers.get("HX-Request"):
                return _hx_call_error("Call is no longer available")
            return JSONResponse({"error": "Call is no longer available"}, status_code=409)

        # Verify user is the recipient
        if call_log.student_id != current_user.id and call_log.supervisor_id != current_user.id:
            if request.headers.get("HX-Request"):
                return _hx_call_error("Unauthorized")
            return JSONResponse({"error": "Unauthorized"}, status_code=403)

        initiator_id = _extract_initiator_id(call_log.notes)
        if initiator_id and current_user.id == initiator_id:
            if request.headers.get("HX-Request"):
                return _hx_call_error("Only the recipient can decline this call")
            return JSONResponse({"error": "Only the recipient can decline this call"}, status_code=403)
        
        # Update call status
        call_log.status = "declined"
        call_log.ended_at = datetime.utcnow()
        db.commit()
        
        # Notify caller that call was declined
        caller_id = call_log.supervisor_id if current_user.role == UserRole.STUDENT else call_log.student_id
        
        await notification_manager.send_to_user(
            caller_id,
            "call_cancelled",
            {"call_id": call_id, "reason": "declined"}
        )

        try:
            notif_service = NotificationService(db)
            fallback_url = "/student/communication?tab=calls" if current_user.role == UserRole.SUPERVISOR else "/supervisor/communication?tab=calls"
            notif_service.create_notification(
                user_id=caller_id,
                notification_type=NotificationType.SYSTEM_ANNOUNCEMENT,
                title="Call Declined",
                message=f"{current_user.full_name} declined your call.",
                action_url=fallback_url,
            )
            db.commit()
        except Exception:
            db.rollback()
        
        if request.headers.get("HX-Request"):
            return hx_trigger("call_declined")

        return JSONResponse({"success": True})
    
    @app.get("/student/call/{room_name}")
    @require_auth()
    @require_role(UserRole.STUDENT)
    def student_join_call(
        request: Request,
        room_name: str,
        db: Session = None,
        current_user: Optional[User] = None
    ):
        """Student joins a video call.
        
        Args:
            request: FastHTML request object
            room_name: Daily.co room name
            db: Database session
            current_user: Authenticated user
        
        Returns:
            Video call page with embedded Daily.co iframe
        """
        # Get call log
        call_log = db.query(CallLog).filter(
            CallLog.room_name == room_name,
            CallLog.student_id == current_user.id
        ).first()
        
        if not call_log:
            return Div(
                H1("Call Not Found"),
                P("This call does not exist or you don't have permission to join."),
                A("Back to Dashboard", href="/student/dashboard", cls="btn btn-primary")
            )
        
        # Move to active only after acceptance to avoid racing against recipient accept action.
        if call_log.status in {"scheduled", "accepted"}:
            call_log.status = "active"
            if not call_log.started_at:
                call_log.started_at = datetime.utcnow()
            db.commit()
        
        # Generate meeting token for security
        daily_service = DailyService()
        token = None
        try:
            token = daily_service.create_meeting_token(
                room_name=room_name,
                user_name=current_user.full_name,
                is_owner=False  # Student is not owner
            )
        except Exception:
            token = None

        room_src = call_log.room_url
        if token:
            room_src = f"{call_log.room_url}?t={token}"
        elif daily_service.provider == "jitsi":
            from urllib.parse import quote
            display_name = quote(current_user.full_name or "User", safe="")
            room_src = f"{call_log.room_url}&userInfo.displayName=%22{display_name}%22&config.requireDisplayName=false"
        
        return_url = f"/student/communication?tab=calls&peer_id={call_log.supervisor_id}"
        end_url = f"/api/calls/{call_log.id}/end"
        status_url = f"/api/calls/{call_log.id}/status"
        auto_redirect_statuses = "completed,declined,missed"

        # Return video call page
        return Html(
            Head(
                Title("Video Call - SIWES Logbook"),
                Meta(charset="utf-8"),
                Meta(name="viewport", content="width=device-width, initial-scale=1"),
                Style("""
                    body { margin: 0; padding: 0; overflow: hidden; }
                    #call-frame { width: 100vw; height: 100vh; border: none; }
                    #call-overlay {
                        position: fixed;
                        top: 12px;
                        right: 12px;
                        z-index: 1000;
                        display: flex;
                        gap: 8px;
                    }
                    #end-return-btn {
                        border: none;
                        border-radius: 999px;
                        background: rgba(220, 53, 69, 0.92);
                        color: #fff;
                        padding: 10px 14px;
                        font-weight: 600;
                        cursor: pointer;
                        backdrop-filter: blur(6px);
                    }
                """)
            ),
            Body(
                Div(
                    Button("End & Return", id="end-return-btn"),
                    id="call-overlay",
                ),
                Iframe(
                    id="call-frame",
                    src=room_src,
                    allow="camera; microphone; fullscreen; speaker; display-capture"
                ),
                Script(f"""
                    (function() {{
                        const returnUrl = "{return_url}";
                        const endUrl = "{end_url}";
                        const statusUrl = "{status_url}";
                        const terminalStatuses = new Set("{auto_redirect_statuses}".split(","));
                        let redirecting = false;

                        function goBack() {{
                            if (redirecting) return;
                            redirecting = true;
                            window.location.href = returnUrl;
                        }}

                        async function endAndReturn() {{
                            try {{
                                await fetch(endUrl, {{
                                    method: "POST",
                                    credentials: "same-origin"
                                }});
                            }} catch (e) {{
                                console.error("[CALL] Failed to end call:", e);
                            }} finally {{
                                goBack();
                            }}
                        }}

                        async function checkStatus() {{
                            if (redirecting) return;
                            try {{
                                const response = await fetch(statusUrl, {{ credentials: "same-origin" }});
                                if (!response.ok) return;
                                const data = await response.json();
                                if (data && terminalStatuses.has(String(data.status || ""))) {{
                                    goBack();
                                }}
                            }} catch (e) {{
                                console.error("[CALL] Status check failed:", e);
                            }}
                        }}

                        const btn = document.getElementById("end-return-btn");
                        if (btn) btn.addEventListener("click", endAndReturn);
                        window.addEventListener("beforeunload", function() {{
                            try {{
                                navigator.sendBeacon(endUrl);
                            }} catch (e) {{
                                console.error("[CALL] beforeunload beacon failed:", e);
                            }}
                        }});
                        setInterval(checkStatus, 5000);
                    }})();
                """)
            )
        )
    
    @app.get("/supervisor/call/{room_name}")
    @require_auth()
    @require_role(UserRole.SUPERVISOR)
    def supervisor_join_call(
        request: Request,
        room_name: str,
        db: Session = None,
        current_user: Optional[User] = None
    ):
        """Supervisor joins a video call.
        
        Args:
            request: FastHTML request object
            room_name: Daily.co room name
            db: Database session
            current_user: Authenticated user
        
        Returns:
            Video call page with embedded Daily.co iframe
        """
        # Get call log
        call_log = db.query(CallLog).filter(
            CallLog.room_name == room_name,
            CallLog.supervisor_id == current_user.id
        ).first()
        
        if not call_log:
            return Div(
                H1("Call Not Found"),
                P("This call does not exist or you don't have permission to join."),
                A("Back to Dashboard", href="/supervisor/dashboard", cls="btn btn-primary")
            )
        
        # Move to active only after acceptance to avoid racing against recipient accept action.
        if call_log.status in {"scheduled", "accepted"}:
            call_log.status = "active"
            if not call_log.started_at:
                call_log.started_at = datetime.utcnow()
            db.commit()
        
        # Generate meeting token for security
        daily_service = DailyService()
        token = None
        try:
            token = daily_service.create_meeting_token(
                room_name=room_name,
                user_name=current_user.full_name,
                is_owner=True  # Supervisor is owner (can record, eject)
            )
        except Exception:
            token = None

        room_src = call_log.room_url
        if token:
            room_src = f"{call_log.room_url}?t={token}"
        elif daily_service.provider == "jitsi":
            from urllib.parse import quote
            display_name = quote(current_user.full_name or "User", safe="")
            room_src = f"{call_log.room_url}&userInfo.displayName=%22{display_name}%22&config.requireDisplayName=false"
        
        return_url = f"/supervisor/communication?tab=calls&student_id={call_log.student_id}&peer_id={call_log.student_id}"
        end_url = f"/api/calls/{call_log.id}/end"
        status_url = f"/api/calls/{call_log.id}/status"
        auto_redirect_statuses = "completed,declined,missed"

        # Return video call page
        return Html(
            Head(
                Title("Video Call - SIWES Logbook"),
                Meta(charset="utf-8"),
                Meta(name="viewport", content="width=device-width, initial-scale=1"),
                Style("""
                    body { margin: 0; padding: 0; overflow: hidden; }
                    #call-frame { width: 100vw; height: 100vh; border: none; }
                    #call-overlay {
                        position: fixed;
                        top: 12px;
                        right: 12px;
                        z-index: 1000;
                        display: flex;
                        gap: 8px;
                    }
                    #end-return-btn {
                        border: none;
                        border-radius: 999px;
                        background: rgba(220, 53, 69, 0.92);
                        color: #fff;
                        padding: 10px 14px;
                        font-weight: 600;
                        cursor: pointer;
                        backdrop-filter: blur(6px);
                    }
                """)
            ),
            Body(
                Div(
                    Button("End & Return", id="end-return-btn"),
                    id="call-overlay",
                ),
                Iframe(
                    id="call-frame",
                    src=room_src,
                    allow="camera; microphone; fullscreen; speaker; display-capture"
                ),
                Script(f"""
                    (function() {{
                        const returnUrl = "{return_url}";
                        const endUrl = "{end_url}";
                        const statusUrl = "{status_url}";
                        const terminalStatuses = new Set("{auto_redirect_statuses}".split(","));
                        let redirecting = false;

                        function goBack() {{
                            if (redirecting) return;
                            redirecting = true;
                            window.location.href = returnUrl;
                        }}

                        async function endAndReturn() {{
                            try {{
                                await fetch(endUrl, {{
                                    method: "POST",
                                    credentials: "same-origin"
                                }});
                            }} catch (e) {{
                                console.error("[CALL] Failed to end call:", e);
                            }} finally {{
                                goBack();
                            }}
                        }}

                        async function checkStatus() {{
                            if (redirecting) return;
                            try {{
                                const response = await fetch(statusUrl, {{ credentials: "same-origin" }});
                                if (!response.ok) return;
                                const data = await response.json();
                                if (data && terminalStatuses.has(String(data.status || ""))) {{
                                    goBack();
                                }}
                            }} catch (e) {{
                                console.error("[CALL] Status check failed:", e);
                            }}
                        }}

                        const btn = document.getElementById("end-return-btn");
                        if (btn) btn.addEventListener("click", endAndReturn);
                        window.addEventListener("beforeunload", function() {{
                            try {{
                                navigator.sendBeacon(endUrl);
                            }} catch (e) {{
                                console.error("[CALL] beforeunload beacon failed:", e);
                            }}
                        }});
                        setInterval(checkStatus, 5000);
                    }})();
                """)
            )
        )

    @app.get("/api/calls/{call_id}/status")
    @require_auth()
    def call_status(
        request: Request,
        call_id: str,
        db: Session = None,
        current_user: Optional[User] = None
    ):
        """Get call status for participants to support call-page auto return."""
        call_log = db.query(CallLog).filter(CallLog.id == call_id).first()
        if not call_log:
            return JSONResponse({"error": "Call not found"}, status_code=404)
        if call_log.student_id != current_user.id and call_log.supervisor_id != current_user.id:
            return JSONResponse({"error": "Unauthorized"}, status_code=403)
        return JSONResponse({"call_id": call_id, "status": call_log.status})
    
    @app.post("/api/calls/{call_id}/end")
    @require_auth()
    def end_call(
        request: Request,
        call_id: str,
        db: Session = None,
        current_user: Optional[User] = None
    ):
        """End a video call and update duration.
        
        Args:
            request: FastHTML request object
            call_id: Call log ID
            db: Database session
            current_user: Authenticated user
        
        Returns:
            JSON response with success status
        """
        # Get call log
        call_log = db.query(CallLog).filter(CallLog.id == call_id).first()
        
        if not call_log:
            return JSONResponse({"error": "Call not found"}, status_code=404)
        
        # Verify user is participant
        if call_log.student_id != current_user.id and call_log.supervisor_id != current_user.id:
            return JSONResponse({"error": "Unauthorized"}, status_code=403)
        
        # Update call log
        call_log.ended_at = datetime.utcnow()
        call_log.status = "completed"
        
        # Calculate duration
        if call_log.started_at:
            duration = (call_log.ended_at - call_log.started_at).total_seconds() / 60
            call_log.duration_minutes = int(duration)
        
        db.commit()
        
        # Delete Daily.co room
        try:
            daily_service = DailyService()
            daily_service.delete_room(call_log.room_name)
        except Exception as e:
            # Log error but don't fail the request
            print(f"Failed to delete Daily.co room: {e}")
        
        return JSONResponse({
            "success": True,
            "duration_minutes": call_log.duration_minutes
        })


def _extract_initiator_id(notes: str | None) -> str | None:
    """Extract initiator user ID from CallLog notes metadata."""
    if not notes:
        return None
    prefix = "initiator:"
    if notes.startswith(prefix):
        return notes[len(prefix):]
    return None
