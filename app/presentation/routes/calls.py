"""Video call routes for LiveKit integration."""

from fasthtml.common import *
from sqlalchemy.orm import Session
from datetime import datetime
import asyncio
import json
from typing import Optional

from app.infrastructure.security.session import require_auth, require_role
from app.application.services.daily import LiveKitService
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


def _call_log_url_for_role(role: UserRole, call_log: CallLog) -> str:
    """Build role-safe call history URL for notifications."""
    if role == UserRole.STUDENT:
        return f"/student/communication?tab=calls&peer_id={call_log.supervisor_id}"
    return f"/supervisor/communication?tab=calls&student_id={call_log.student_id}&peer_id={call_log.student_id}"


def _render_livekit_call_page(
    *,
    page_title: str,
    livekit_ws_url: str,
    token: str,
    room_name: str,
    display_name: str,
    video_enabled: bool,
    return_url: str,
    end_url: str,
    status_url: str,
    auto_redirect_statuses: str = "completed,declined,missed",
):
    """Render an in-app LiveKit call page with zero prejoin config."""
    ws_url_js = json.dumps(livekit_ws_url)
    token_js = json.dumps(token)
    room_js = json.dumps(room_name)
    display_name_js = json.dumps(display_name)
    return_url_js = json.dumps(return_url)
    end_url_js = json.dumps(end_url)
    status_url_js = json.dumps(status_url)
    statuses_js = json.dumps(auto_redirect_statuses.split(","))
    mode_js = "video" if video_enabled else "voice"

    return Html(
        Head(
            Title(page_title),
            Meta(charset="utf-8"),
            Meta(name="viewport", content="width=device-width, initial-scale=1"),
            Style(
                """
                :root {
                    --call-bg: radial-gradient(1200px 600px at 20% 10%, rgba(13,110,253,.12), transparent), #0f172a;
                    --panel-bg: rgba(255,255,255,0.08);
                    --panel-border: rgba(255,255,255,0.15);
                }
                body { margin: 0; background: var(--call-bg); color: #e2e8f0; font-family: system-ui, sans-serif; }
                .call-shell { min-height: 100vh; display: flex; flex-direction: column; }
                .call-top {
                    display: flex; align-items: center; justify-content: space-between;
                    padding: 12px 16px; backdrop-filter: blur(10px);
                    background: rgba(15, 23, 42, 0.55); border-bottom: 1px solid var(--panel-border);
                }
                .call-meta { font-size: .9rem; color: #cbd5e1; }
                .call-stage { flex: 1; display: grid; grid-template-columns: 1fr; gap: 12px; padding: 12px; }
                .media-panel {
                    border: 1px solid var(--panel-border); border-radius: 14px;
                    background: var(--panel-bg); overflow: hidden; min-height: 240px;
                }
                .media-title { padding: 8px 10px; font-size: .78rem; color: #94a3b8; border-bottom: 1px solid var(--panel-border); }
                .media-body { position: relative; height: calc(100% - 34px); }
                .media-body video, .media-body audio { width: 100%; height: 100%; object-fit: cover; display: block; }
                .voice-center {
                    min-height: 220px; display: flex; flex-direction: column;
                    align-items: center; justify-content: center; gap: 8px; color: #cbd5e1;
                }
                .voice-avatar {
                    width: 88px; height: 88px; border-radius: 50%;
                    display: flex; align-items: center; justify-content: center;
                    background: rgba(59,130,246,.25); border: 1px solid rgba(148,163,184,.4);
                    font-weight: 700; font-size: 1.25rem;
                }
                .call-controls {
                    display: flex; justify-content: center; gap: 10px; padding: 12px 16px 18px;
                }
                .call-btn {
                    border: none; border-radius: 999px; padding: 10px 14px;
                    font-weight: 600; cursor: pointer; color: #fff;
                    background: rgba(30, 41, 59, 0.9);
                }
                .call-btn.danger { background: rgba(220, 53, 69, 0.95); }
                .call-btn.active { background: rgba(13, 110, 253, 0.92); }
                .call-status { padding: 0 16px 10px; text-align: center; color: #94a3b8; font-size: .9rem; }
                .audio-unlock {
                    position: fixed; inset: 0; z-index: 30;
                    display: flex; align-items: center; justify-content: center;
                    padding: 18px; background: rgba(15, 23, 42, 0.72);
                    backdrop-filter: blur(12px);
                }
                .audio-unlock.d-none { display: none; }
                .audio-card {
                    width: min(420px, 100%); border-radius: 18px; padding: 22px;
                    background: rgba(255, 255, 255, 0.96); color: #0f172a;
                    box-shadow: 0 24px 70px rgba(0,0,0,.35);
                    text-align: center;
                }
                .audio-card p { color: #475569; margin: 8px 0 18px; }
                .audio-card button {
                    border: none; border-radius: 999px; padding: 11px 18px;
                    background: #2563eb; color: #fff; font-weight: 700;
                }
                @media (max-width: 900px) {
                    .call-stage { grid-template-columns: 1fr; }
                }
                """
            ),
        ),
        Body(
            Div(
                Div(
                    Div(
                        Div("Live Call", cls="fw-semibold"),
                        Div(
                            f"{'Video' if video_enabled else 'Voice'} - {display_name}",
                            cls="call-meta",
                        ),
                    ),
                    Div(f"Room: {room_name}", cls="call-meta"),
                    cls="call-top",
                ),
                Div(
                    Div(
                        Div("Remote Participant", cls="media-title"),
                        Div(
                            Div(
                                Div("Waiting for other participant...", cls="small"),
                                Div("Audio will connect automatically.", cls="small text-muted"),
                                cls="voice-center",
                                id="remote-voice-state",
                            ),
                            id="remote-media",
                            cls="media-body",
                        ),
                        cls="media-panel",
                    ),
                    cls="call-stage",
                ),
                Div(id="call-status", cls="call-status", *["Connecting..."]),
                Div(
                    Div(
                        H3("Enable call audio", cls="mb-2"),
                        P("Your browser blocked automatic audio. Tap below so microphone and speaker audio can start."),
                        Button("Enable Audio", id="enable-audio-btn", type="button"),
                        cls="audio-card",
                    ),
                    id="audio-unlock-overlay",
                    cls="audio-unlock d-none",
                ),
                Div(
                    Button("Mute", id="mute-btn", cls="call-btn active"),
                    Button(
                        "Camera Off" if video_enabled else "Voice Mode",
                        id="video-btn",
                        cls="call-btn" + ("" if video_enabled else " d-none"),
                    ),
                    Button("End & Return", id="end-btn", cls="call-btn danger"),
                    cls="call-controls",
                ),
                cls="call-shell",
            ),
            Script(
                f"""
                import {{ Room, RoomEvent }} from 'https://cdn.jsdelivr.net/npm/livekit-client@2.15.4/dist/livekit-client.esm.mjs';

                const wsUrl = {ws_url_js};
                const token = {token_js};
                const roomName = {room_js};
                const displayName = {display_name_js};
                const returnUrl = {return_url_js};
                const endUrl = {end_url_js};
                const statusUrl = {status_url_js};
                const terminalStatuses = new Set({statuses_js});
                const callMode = "{mode_js}";

                const statusEl = document.getElementById('call-status');
                const remoteMedia = document.getElementById('remote-media');
                const muteBtn = document.getElementById('mute-btn');
                const videoBtn = document.getElementById('video-btn');
                const endBtn = document.getElementById('end-btn');
                const audioOverlay = document.getElementById('audio-unlock-overlay');
                const enableAudioBtn = document.getElementById('enable-audio-btn');

                let redirecting = false;
                let micEnabled = true;
                let camEnabled = callMode === 'video';

                const room = new Room({{
                    adaptiveStream: true,
                    dynacast: true,
                    audioCaptureDefaults: {{
                        echoCancellation: true,
                        noiseSuppression: true,
                        autoGainControl: true,
                    }},
                    audioOutput: {{ deviceId: 'default' }},
                }});

                function setStatus(message) {{
                    if (statusEl) statusEl.textContent = message;
                }}

                function showAudioUnlock(message) {{
                    if (message) setStatus(message);
                    if (audioOverlay) audioOverlay.classList.remove('d-none');
                }}

                function hideAudioUnlock() {{
                    if (audioOverlay) audioOverlay.classList.add('d-none');
                }}

                function goBack() {{
                    if (redirecting) return;
                    redirecting = true;
                    window.location.href = returnUrl;
                }}

                async function endAndReturn() {{
                    try {{
                        await fetch(endUrl, {{
                            method: 'POST',
                            credentials: 'same-origin',
                        }});
                    }} catch (e) {{
                        console.error('[CALL] Failed to end call:', e);
                    }} finally {{
                        try {{ room.disconnect(); }} catch (_) {{}}
                        goBack();
                    }}
                }}

                async function checkStatus() {{
                    if (redirecting) return;
                    try {{
                        const response = await fetch(statusUrl, {{ credentials: 'same-origin' }});
                        if (!response.ok) return;
                        const data = await response.json();
                        const st = String((data && data.status) || '');
                        if (terminalStatuses.has(st)) goBack();
                    }} catch (e) {{
                        console.error('[CALL] Status check failed:', e);
                    }}
                }}

                function clearRemoteMedia() {{
                    const nodes = remoteMedia ? remoteMedia.querySelectorAll('video,audio') : [];
                    nodes.forEach(n => n.remove());
                    const wait = document.getElementById('remote-voice-state');
                    if (wait) wait.classList.remove('d-none');
                }}

                function attachRemoteTrack(track) {{
                    if (!remoteMedia) return;
                    const wait = document.getElementById('remote-voice-state');
                    if (wait) wait.classList.add('d-none');
                    const el = track.attach();
                    el.autoplay = true;
                    el.playsInline = true;
                    if (track.kind === 'audio') {{
                        el.muted = false;
                        el.volume = 1.0;
                        el.controls = false;
                    }}
                    remoteMedia.appendChild(el);
                    if (track.kind === 'audio') {{
                        // Attempt immediate play, then retry after 500ms for autoplay restrictions
                        el.play().then(hideAudioUnlock).catch(() => {{
                            setTimeout(() => {{
                                el.play().then(hideAudioUnlock).catch(() => {{
                                    showAudioUnlock('Tap \'Enable Audio\' to hear the other participant.');
                                }});
                            }}, 500);
                        }});
                    }}
                }}

                async function enableAudioPlayback() {{
                    try {{
                        if (room.startAudio) await room.startAudio();
                        const media = remoteMedia ? remoteMedia.querySelectorAll('audio,video') : [];
                        for (const el of media) {{
                            if (el.play) {{
                                try {{ await el.play(); }} catch (_) {{}}
                            }}
                        }}
                        hideAudioUnlock();
                        setStatus(room.remoteParticipants.size > 0 ? 'Connected' : 'Waiting for other participant...');
                    }} catch (e) {{
                        console.error('[CALL] audio unlock failed', e);
                        showAudioUnlock('Audio is still blocked. Check browser permissions and tap Enable Audio again.');
                    }}
                }}

                async function enableLocalTracks() {{
                    try {{
                        await room.localParticipant.setMicrophoneEnabled(true);
                        micEnabled = true;
                        muteBtn.textContent = 'Mute';
                        muteBtn.classList.add('active');
                    }} catch (e) {{
                        console.error('[CALL] microphone permission failed', e);
                        micEnabled = false;
                        muteBtn.textContent = 'Unmute';
                        muteBtn.classList.remove('active');
                        showAudioUnlock('Microphone permission is required. Allow microphone access, then tap Enable Audio.');
                        throw e;
                    }}

                    if (callMode === 'video') {{
                        try {{
                            await room.localParticipant.setCameraEnabled(true);
                            camEnabled = true;
                            videoBtn.textContent = 'Camera Off';
                            videoBtn.classList.add('active');
                        }} catch (e) {{
                            console.error('[CALL] camera permission failed', e);
                            setStatus('Camera unavailable. Audio call is still active.');
                            camEnabled = false;
                            videoBtn.textContent = 'Camera On';
                            videoBtn.classList.remove('active');
                        }}
                    }} else {{
                        await room.localParticipant.setCameraEnabled(false);
                    }}
                }}

                room.on(RoomEvent.TrackSubscribed, (track) => {{
                    attachRemoteTrack(track);
                    setStatus('Connected');
                }});

                room.on(RoomEvent.TrackUnsubscribed, (track) => {{
                    try {{ track.detach().forEach(el => el.remove()); }} catch (_) {{}}
                    const hasMedia = !!remoteMedia.querySelector('video,audio');
                    if (!hasMedia) clearRemoteMedia();
                }});

                room.on(RoomEvent.ParticipantConnected, () => {{
                    setStatus('Connected');
                }});

                room.on(RoomEvent.ParticipantDisconnected, () => {{
                    if (room.remoteParticipants.size === 0) {{
                        clearRemoteMedia();
                        setStatus('Other participant left');
                        setTimeout(endAndReturn, 1200);
                    }}
                }});

                room.on(RoomEvent.Disconnected, () => {{
                    goBack();
                }});

                muteBtn?.addEventListener('click', async () => {{
                    micEnabled = !micEnabled;
                    try {{
                        await room.localParticipant.setMicrophoneEnabled(micEnabled);
                        muteBtn.textContent = micEnabled ? 'Mute' : 'Unmute';
                        muteBtn.classList.toggle('active', micEnabled);
                    }} catch (e) {{
                        console.error('[CALL] mic toggle failed', e);
                    }}
                }});

                videoBtn?.addEventListener('click', async () => {{
                    if (callMode !== 'video') return;
                    camEnabled = !camEnabled;
                    try {{
                        await room.localParticipant.setCameraEnabled(camEnabled);
                        videoBtn.textContent = camEnabled ? 'Camera Off' : 'Camera On';
                        videoBtn.classList.toggle('active', camEnabled);
                    }} catch (e) {{
                        console.error('[CALL] cam toggle failed', e);
                    }}
                }});

                endBtn?.addEventListener('click', endAndReturn);
                enableAudioBtn?.addEventListener('click', async () => {{
                    try {{
                        await room.localParticipant.setMicrophoneEnabled(true);
                        micEnabled = true;
                        muteBtn.textContent = 'Mute';
                        muteBtn.classList.add('active');
                    }} catch (e) {{
                        console.error('[CALL] microphone retry failed', e);
                        showAudioUnlock('Microphone is still blocked. Please allow microphone permission in the browser.');
                        return;
                    }}
                    await enableAudioPlayback();
                }});

                window.addEventListener('beforeunload', () => {{
                    try {{ navigator.sendBeacon(endUrl); }} catch (_) {{}}
                }});

                async function start() {{
                    try {{
                        setStatus('Connecting to room...');
                        await room.connect(wsUrl, token);
                        await enableLocalTracks();
                        await enableAudioPlayback();

                        if (room.remoteParticipants.size > 0) {{
                            setStatus('Connected');
                        }} else {{
                            setStatus('Waiting for other participant...');
                        }}
                    }} catch (e) {{
                        console.error('[CALL] connect failed', e);
                        setStatus('Unable to connect. Returning...');
                        setTimeout(goBack, 1200);
                    }}
                }}

                start();
                setInterval(checkStatus, 5000);
                """,
                **{"type": "module"},
            ),
        ),
    )


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
        caller_role = UserRole.STUDENT if caller_id == call_log.student_id else UserRole.SUPERVISOR
        callback_url = _call_log_url_for_role(caller_role, call_log)

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
        created_local_session = False
        if not db:
            from app.infrastructure.database.connection import SessionLocal
            db = SessionLocal()
            created_local_session = True
        
        from app.domain.models.user import User
        
        current_user = db.query(User).filter(User.id == request.session["user_id"]).first()
        if not current_user:
            if created_local_session:
                db.close()
            return JSONResponse(
                {"error": "User not found"},
                status_code=404,
                headers={"Content-Type": "application/json"}
            )
        
        # Only students and supervisors can initiate calls
        if current_user.role not in [UserRole.STUDENT, UserRole.SUPERVISOR]:
            if created_local_session:
                db.close()
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

            # Create LiveKit room handle
            daily_service = LiveKitService()
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
                    action_url = _call_log_url_for_role(UserRole.SUPERVISOR, call_log)
                else:
                    action_url = _call_log_url_for_role(UserRole.STUDENT, call_log)
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
        finally:
            if created_local_session:
                db.close()
    
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

        # Idempotent accept for repeated click/retry on already-accepted calls.
        if call_log.status == "accepted":
            redirect_url = _build_join_url_for_user(
                current_user.role, call_log.room_name, call_log.call_type or "video"
            )
            if request.headers.get("HX-Request"):
                return hx_redirect(redirect_url)
            return JSONResponse({"success": True, "redirect_url": redirect_url})

        if call_log.status != "ringing":
            if request.headers.get("HX-Request"):
                return _hx_call_error("Call is no longer available")
            return JSONResponse({"error": "Call is no longer available"}, status_code=409)
        
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
            caller_role = UserRole.SUPERVISOR if caller_id == call_log.supervisor_id else UserRole.STUDENT
            notif_service.create_notification(
                user_id=caller_id,
                notification_type=NotificationType.SYSTEM_ANNOUNCEMENT,
                title="Call Accepted",
                message=f"{current_user.full_name} accepted your call.",
                action_url=_call_log_url_for_role(caller_role, call_log),
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

        # Idempotent success when already terminal.
        if call_log.status in {"declined", "missed", "completed", "cancelled"}:
            if request.headers.get("HX-Request"):
                return hx_trigger("call_declined")
            return JSONResponse({"success": True})

        if call_log.status != "ringing":
            if request.headers.get("HX-Request"):
                return _hx_call_error("Call is no longer available")
            return JSONResponse({"error": "Call is no longer available"}, status_code=409)
        
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
            caller_role = UserRole.SUPERVISOR if caller_id == call_log.supervisor_id else UserRole.STUDENT
            fallback_url = _call_log_url_for_role(caller_role, call_log)
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
            room_name: LiveKit room name
            db: Database session
            current_user: Authenticated user
        
        Returns:
            Video call page with embedded LiveKit UI
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
        daily_service = LiveKitService()
        try:
            token = daily_service.create_meeting_token(
                room_name=room_name,
                user_name=current_user.full_name,
                is_owner=False,  # Student is not owner
                identity=current_user.id,
            )
        except Exception as e:
            return Div(
                H1("Unable to start call"),
                P(f"Token generation failed: {str(e)}"),
                A("Back", href="/student/communication?tab=calls", cls="btn btn-primary"),
                cls="container py-5",
            )

        video_enabled = (call_log.call_type or "video") != "voice"
        video_query = (request.query_params.get("video") or "").strip().lower()
        if video_query in {"false", "0", "no"}:
            video_enabled = False

        return_url = f"/student/communication?tab=calls&peer_id={call_log.supervisor_id}"
        end_url = f"/api/calls/{call_log.id}/end"
        status_url = f"/api/calls/{call_log.id}/status"
        return _render_livekit_call_page(
            page_title=("Video Call - SIWES Logbook" if video_enabled else "Voice Call - SIWES Logbook"),
            livekit_ws_url=daily_service.livekit_url,
            token=token,
            room_name=room_name,
            display_name=current_user.full_name,
            video_enabled=video_enabled,
            return_url=return_url,
            end_url=end_url,
            status_url=status_url,
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
            room_name: LiveKit room name
            db: Database session
            current_user: Authenticated user
        
        Returns:
            Video call page with embedded LiveKit UI
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
        daily_service = LiveKitService()
        try:
            token = daily_service.create_meeting_token(
                room_name=room_name,
                user_name=current_user.full_name,
                is_owner=True,  # Supervisor is owner
                identity=current_user.id,
            )
        except Exception as e:
            return Div(
                H1("Unable to start call"),
                P(f"Token generation failed: {str(e)}"),
                A("Back", href="/supervisor/communication?tab=calls", cls="btn btn-primary"),
                cls="container py-5",
            )

        video_enabled = (call_log.call_type or "video") != "voice"
        video_query = (request.query_params.get("video") or "").strip().lower()
        if video_query in {"false", "0", "no"}:
            video_enabled = False

        return_url = f"/supervisor/communication?tab=calls&student_id={call_log.student_id}&peer_id={call_log.student_id}"
        end_url = f"/api/calls/{call_log.id}/end"
        status_url = f"/api/calls/{call_log.id}/status"
        return _render_livekit_call_page(
            page_title=("Video Call - SIWES Logbook" if video_enabled else "Voice Call - SIWES Logbook"),
            livekit_ws_url=daily_service.livekit_url,
            token=token,
            room_name=room_name,
            display_name=current_user.full_name,
            video_enabled=video_enabled,
            return_url=return_url,
            end_url=end_url,
            status_url=status_url,
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
        
        # LiveKit rooms are ephemeral; delete_room is a no-op.
        try:
            daily_service = LiveKitService()
            daily_service.delete_room(call_log.room_name)
        except Exception as e:
            # Log error but don't fail the request
            print(f"Failed to finalize room cleanup: {e}")
        
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
