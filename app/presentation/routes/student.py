from fasthtml.common import *
from typing import Optional, List, Dict
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_, desc
from datetime import date, datetime, timedelta
from app.domain.models.user import User, UserRole
from app.infrastructure.security.session import require_auth, require_role
from app.domain.models.log import DailyLog, LogStatus
from app.domain.models.chat import Notification, NotificationType
from app.application.services.log import LogService
from app.presentation.components.domain.student.dashboard import StudentDashboard
from app.presentation.components.domain.student.logbook import (
    LogbookPage,
    WeekCard,
    LogEntryModalBody,
    LogAccessBlockedModalBody,
    FilterTabs,
)
from app.presentation.components.domain.student.communication import CommunicationPage
from app.presentation.components.domain.student.profile import StudentProfilePage, SettingsCard
from app.presentation.components.ui.layouts import DashboardLayout
from app.presentation.components.ui.navigation import StudentSidebarNav, StudentBottomNav
from app.infrastructure.repositories.placement import PlacementRepository
from app.application.services.sync import SyncService
from app.application.services.notifications import notification_manager
from app.application.services.notification import NotificationService
from app.domain.models.user import StudentProfile
from app.domain.models.placement import IndustrialPlacement
from app.infrastructure.services.geofence import GeofenceService


def setup_student_routes(app: FastHTML):
    """Setup student routes.
    
    Args:
        app: FastHTML application instance
    """
    
    @app.get("/student/dashboard")
    @require_auth()
    @require_role(UserRole.STUDENT)
    def student_dashboard(request: Request, db: Session = None, current_user: Optional[User] = None):
        """Student dashboard page.
        
        Args:
            request: FastHTML request object
            db: Database session
            current_user: Authenticated user (injected)
        
        Returns:
            Dashboard HTML
        """
        user_name = current_user.full_name if current_user else "Student"
        current_week = _calculate_current_week(db, current_user.id)
        student_profile = db.query(StudentProfile).filter(StudentProfile.user_id == current_user.id).first()
        placement = PlacementRepository(db).get_active_placement(current_user.id)
        logs = LogService(db).get_student_logs(current_user.id, placement.id) if placement else []

        verified = sum(1 for log in logs if _status_key(log.status) == "verified")
        pending = sum(1 for log in logs if _status_key(log.status) == "pending_review")
        flagged = sum(1 for log in logs if _status_key(log.status) == "flagged")
        total_logs = len(logs)
        hours = total_logs * 8
        missed = _calculate_missed_logs(student_profile, logs)

        current_week_logs = [log for log in logs if log.week_number == current_week]
        days_logged_this_week = len(current_week_logs)

        most_recent_log = logs[0] if logs else None
        if most_recent_log:
            last_entry_label = (
                f"{most_recent_log.log_date.strftime('%b %d')}, "
                f"{most_recent_log.created_at.strftime('%I:%M %p') if most_recent_log.created_at else '--:--'}"
            )
        else:
            last_entry_label = "No entry yet"

        completion_percent = min(int(round((total_logs / 125) * 100)), 100)
        week_progress_percent = min(int(round((current_week / 25) * 100)), 100)

        placement_ids = {log.placement_id for log in logs if log.placement_id}
        placement_radius_by_id: dict[str, float] = {}
        if placement_ids:
            placements = db.query(IndustrialPlacement).filter(IndustrialPlacement.id.in_(placement_ids)).all()
            for p in placements:
                if p.geofence:
                    placement_radius_by_id[p.id] = float(p.geofence.radius_meters)

        location_scores: list[int] = []
        location_within_count = 0
        for log in logs:
            score = _location_proximity_score(
                distance_from_geofence=getattr(log, "distance_from_geofence", None),
                radius_meters=placement_radius_by_id.get(log.placement_id),
                location_status=_location_key(log.location_status),
            )
            if score is None:
                continue
            location_scores.append(score)
            if score >= 100:
                location_within_count += 1

        location_total_count = len(location_scores)
        location_accuracy_percent = int(round(sum(location_scores) / location_total_count)) if location_total_count else 0

        recent_activities = []
        for log in logs[:5]:
            description = (log.activity_description or "").strip()
            if len(description) > 80:
                description = f"{description[:77]}..."
            location_key = _location_key(log.location_status)
            if location_key == "within":
                location_label = "Within geofence"
            elif location_key == "outside":
                location_label = "Outside geofence"
            else:
                location_label = "Location unknown"

            recent_activities.append(
                {
                    "date": log.log_date,
                    "description": description or "No description",
                    "week_number": log.week_number,
                    "location_label": location_label,
                    "status": _status_key(log.status),
                }
            )

        content = StudentDashboard(
            user_name=user_name,
            current_week=current_week,
            verified=verified,
            pending=pending,
            flagged=flagged,
            missed=missed,
            hours=hours,
            completion_percent=completion_percent,
            week_progress_percent=week_progress_percent,
            days_logged_this_week=days_logged_this_week,
            last_entry_label=last_entry_label,
            location_accuracy_percent=location_accuracy_percent,
            location_within_count=location_within_count,
            location_total_count=location_total_count,
            recent_activities=recent_activities,
        )

        return DashboardLayout(
            content,
            sidebar=StudentSidebarNav(active_page="dashboard"),
            bottom_nav=StudentBottomNav(active_page="dashboard"),
            current_user=current_user,
        )
    
    @app.get("/student/communication")
    @require_auth()
    @require_role(UserRole.STUDENT)
    def student_communication(request: Request, tab: str = "chat", db: Session = None, current_user: Optional[User] = None):
        """Student communication page.
        
        Args:
            request: FastHTML request object
            tab: Active tab (chat or calls)
            db: Database session
        
        Returns:
            Communication page HTML or HTMX partial
        """
        tab = "calls" if tab == "calls" else "chat"
        # Fetch real supervisor data
        from app.domain.models.user import StudentProfile, User
        
        student_profile = db.query(StudentProfile).filter(StudentProfile.user_id == current_user.id).first()
        supervisor_data = None
        
        if student_profile and student_profile.assigned_supervisor_id:
            supervisor = db.query(User).filter(User.id == student_profile.assigned_supervisor_id).first()
            if supervisor:
                is_online = supervisor.id in set(notification_manager.get_active_users())
                supervisor_data = {
                    "id": supervisor.id,
                    "name": supervisor.full_name,
                    "department": student_profile.department, # Assuming same dept
                    "status": "Online" if is_online else "Offline"
                }
        
        # Default fallback
        if not supervisor_data:
            supervisor_data = {
                "id": "",
                "name": "No Supervisor Assigned",
                "department": "N/A",
                "status": "Offline"
            }
            
        # Fetch Chat History
        messages = []
        has_more_messages = False
        oldest_message_at = None
        if supervisor_data.get("id"):
            from app.domain.models.chat import ChatMessage
            
            sup_id = supervisor_data["id"]
            # Mark incoming messages in this conversation as read.
            db.query(ChatMessage).filter(
                ChatMessage.sender_id == sup_id,
                ChatMessage.receiver_id == current_user.id,
                ChatMessage.is_read == False,
            ).update({"is_read": True}, synchronize_session=False)
            db.query(Notification).filter(
                Notification.user_id == current_user.id,
                Notification.type == NotificationType.MESSAGE_RECEIVED,
                Notification.is_read == False,
                Notification.action_url.like(f"%peer_id={sup_id}%"),
            ).update({"is_read": True}, synchronize_session=False)
            db.commit()

            page_size = 20
            chat_logs_desc = db.query(ChatMessage).filter(
                or_(
                    and_(ChatMessage.sender_id == current_user.id, ChatMessage.receiver_id == sup_id),
                    and_(ChatMessage.sender_id == sup_id, ChatMessage.receiver_id == current_user.id)
                )
            ).order_by(desc(ChatMessage.created_at)).limit(page_size + 1).all()

            has_more_messages = len(chat_logs_desc) > page_size
            visible_logs = list(reversed(chat_logs_desc[:page_size]))
            if visible_logs:
                oldest_message_at = visible_logs[0].created_at.isoformat()
            
            messages = [
                {
                    "text": m.message_body,
                    "time": m.created_at.strftime("%I:%M %p"),
                    "is_me": m.sender_id == current_user.id
                }
                for m in visible_logs
            ]

        calls = []
        if supervisor_data.get("id"):
            from app.domain.models.call import CallLog
            call_logs = db.query(CallLog).filter(
                CallLog.student_id == current_user.id,
                CallLog.supervisor_id == supervisor_data["id"]
            ).order_by(CallLog.started_at.desc()).limit(50).all()

            for call in call_logs:
                initiator_id = _extract_initiator_id(call.notes)
                call_type = "outgoing" if initiator_id == current_user.id else "incoming"
                duration = "Missed" if call.status in {"declined", "missed"} else f"{(call.duration_minutes or 0)} min"
                calls.append(
                    {
                        "name": supervisor_data["name"],
                        "type": call_type,
                        "duration": duration,
                        "time": call.started_at.strftime("%b %d, %I:%M %p"),
                    }
                )

        if tab == "calls":
            db.query(Notification).filter(
                Notification.user_id == current_user.id,
                Notification.is_read == False,
                Notification.action_url.like("%/student/communication?tab=calls%"),
            ).update({"is_read": True}, synchronize_session=False)
            db.commit()

        body = Div(
            CommunicationPage(
                active_tab=tab,
                supervisor=supervisor_data,
                messages=messages,
                calls=calls,
                oldest_message_at=oldest_message_at,
                has_more_messages=has_more_messages,
            ),
            id="student-communication-root",
        )

        if request.headers.get("HX-Request"):
            return body

        return DashboardLayout(
            body,
            sidebar=StudentSidebarNav(active_page="communication"),
            bottom_nav=StudentBottomNav(active_page="communication"),
            current_user=current_user,
        )
    
    @app.get("/student/profile")
    @require_auth()
    @require_role(UserRole.STUDENT)
    def student_profile(request: Request, db: Session = None, current_user: Optional[User] = None):
        """Student profile page.
        
        Args:
            request: FastHTML request object
            db: Database session
        
        Returns:
            Profile page HTML
        """
        from app.domain.models.user import StudentProfile, User
        from app.infrastructure.repositories.placement import PlacementRepository
        
        # Fetch profile
        profile = db.query(StudentProfile).filter(StudentProfile.user_id == current_user.id).first()
        
        # Fetch placement
        placement_repo = PlacementRepository(db)
        placement = placement_repo.get_active_placement(current_user.id)
        
        # Prepare User Data
        weeks = 0
        months = 0
        if profile and profile.siwes_start_date and profile.siwes_end_date:
            delta_days = max((profile.siwes_end_date - profile.siwes_start_date).days + 1, 0)
            weeks = max(round(delta_days / 7), 0)
            months = max(round(delta_days / 30), 0)

        user_data = {
            "name": current_user.full_name,
            "email": current_user.email,
            "matric": profile.matriculation_number if profile else "--",
            "dept": profile.department if profile else "--",
            "inst": profile.institution if profile else "--",
            "start": profile.siwes_start_date.strftime("%B %d, %Y") if profile and profile.siwes_start_date else "--",
            "end": profile.siwes_end_date.strftime("%B %d, %Y") if profile and profile.siwes_end_date else "--",
            "weeks": weeks,
            "months": months,
            "avatar_text": "".join(p[0] for p in current_user.full_name.split()[:2]).upper() if current_user.full_name else "--",
        }
        
        # Prepare Placement Data
        placement_data = None
        if placement:
            # Try to get supervisor name
            supervisor_name = "Not Assigned"
            if profile and profile.assigned_supervisor_id:
                sup = db.query(User).filter(User.id == profile.assigned_supervisor_id).first()
                if sup:
                    supervisor_name = sup.full_name
            
            placement_data = {
                "company": placement.company_name,
                "address": placement.address,
                "supervisor": supervisor_name,
                "radius": f"{placement.geofence.radius_meters} meters" if placement.geofence else "Not set"
            }
        settings_data = {
            "location_service": bool(getattr(profile, "setting_location_service", True)) if profile else True,
            "offline_mode": bool(getattr(profile, "setting_offline_mode", False)) if profile else False,
            "notifications": bool(getattr(profile, "setting_notifications", True)) if profile else True,
        }
            
        content = StudentProfilePage(user=user_data, placement=placement_data, settings=settings_data)
        
        return DashboardLayout(
            content,
            sidebar=StudentSidebarNav(active_page="profile"),
            bottom_nav=StudentBottomNav(active_page="profile"),
            current_user=current_user,
        )

    @app.post("/student/profile/settings")
    @require_auth()
    @require_role(UserRole.STUDENT)
    async def save_student_settings(request: Request, db: Session = None, current_user: Optional[User] = None):
        """Persist student profile preference toggles."""
        form = await request.form()
        location_service = bool(form.get("location_service"))
        offline_mode = bool(form.get("offline_mode"))
        notifications = bool(form.get("notifications"))

        profile = db.query(StudentProfile).filter(StudentProfile.user_id == current_user.id).first()
        if not profile:
            return SettingsCard(
                settings={
                    "location_service": location_service,
                    "offline_mode": offline_mode,
                    "notifications": notifications,
                },
                notice="Profile not found. Settings were not saved.",
                notice_variant="danger",
            )

        profile.setting_location_service = location_service
        profile.setting_offline_mode = offline_mode
        profile.setting_notifications = notifications
        db.commit()

        return SettingsCard(
            settings={
                "location_service": location_service,
                "offline_mode": offline_mode,
                "notifications": notifications,
            },
            notice="Settings saved successfully.",
            notice_variant="success",
        )

    @app.get("/student/logbook")
    @require_auth()
    @require_role(UserRole.STUDENT)
    def student_logbook(request: Request, db: Session = None, current_user: Optional[User] = None):
        """Student logbook page with week cards.
        
        Args:
            request: FastHTML request object
            db: Database session
        
        Returns:
            Logbook page HTML
        """
        weeks_data = _get_weeks_data(db, current_user.id, "all")
        current_week = _calculate_current_week(db, current_user.id)
        student_profile = db.query(StudentProfile).filter(StudentProfile.user_id == current_user.id).first()
        offline_mode_enabled = bool(getattr(student_profile, "setting_offline_mode", False)) if student_profile else False
        
        content = LogbookPage(
            weeks_data=weeks_data,
            current_week=current_week,
            total_weeks=25,
            offline_mode_enabled=offline_mode_enabled,
        )
        
        return DashboardLayout(
            content,
            sidebar=StudentSidebarNav(active_page="logbook"),
            bottom_nav=StudentBottomNav(active_page="logbook"),
            current_user=current_user,
        )
    
    @app.get("/student/logbook/day/{day_date}")
    @require_auth()
    @require_role(UserRole.STUDENT)
    def get_log_modal(request: Request, day_date: str, db: Session = None, current_user: Optional[User] = None):
        """Get modal body content for a specific day.
        
        Args:
            request: FastHTML request object
            day_date: Date string
            db: Database session
        
        Returns:
            Modal body HTML (content only)
        """
        if day_date == "today":
            day_date = date.today().isoformat()

        existing_log = None
        try:
            target_date = date.fromisoformat(day_date)
            today = date.today()
            student_profile = db.query(StudentProfile).filter(StudentProfile.user_id == current_user.id).first()
            location_enabled = bool(getattr(student_profile, "setting_location_service", True)) if student_profile else True

            if target_date > today:
                return LogAccessBlockedModalBody("Sorry future entry not allowed")

            day_log = db.query(DailyLog).filter(
                DailyLog.student_id == current_user.id,
                DailyLog.log_date == target_date,
            ).first()

            if target_date < today and not day_log:
                return LogAccessBlockedModalBody("Log window passed, please contact your supervisor")

            if day_log:
                existing_log = {
                    "status": _status_key(day_log.status) if day_log.status else "",
                    "description": day_log.activity_description,
                    "latitude": day_log.latitude,
                    "longitude": day_log.longitude,
                }

                if target_date < today:
                    existing_log["readonly"] = True
                    existing_log["lock_message"] = "Log window passed, please contact your supervisor"
            elif target_date == today and not location_enabled:
                return LogAccessBlockedModalBody("Location Services is disabled in Profile settings. Enable it to create today's log.")
        except ValueError:
            existing_log = None
        
        return LogEntryModalBody(date=day_date, existing_log=existing_log)
    
    @app.post("/student/logbook/create")
    @require_auth()
    @require_role(UserRole.STUDENT)
    async def create_log_entry(request: Request, db: Session = None, current_user: Optional[User] = None):
        """Create a new log entry.
        
        Args:
            request: FastHTML request object
            db: Database session
        
        Returns:
            Success response or error
        """
        from faststrap import Alert
        from faststrap.presets import hx_trigger
        
        form_data = await request.form()
        
        log_date = form_data.get("log_date")
        activity_description = form_data.get("activity_description")
        latitude = form_data.get("latitude")
        longitude = form_data.get("longitude")

        try:
            parsed_log_date = date.fromisoformat(log_date)
        except Exception:
            err = "Invalid log date submitted."
            return Div(
                Alert(err, variant="danger"),
                Script(f"document.body.dispatchEvent(new CustomEvent('log_save_result', {{ detail: {{ ok: false, message: {err!r} }} }}));"),
                cls="modal-body",
                id="modal-body-content"
            )
        
        # Validate date window
        today = date.today()
        if parsed_log_date > today:
            err = "Sorry future entry not allowed"
            return Div(
                Alert(err, variant="warning"),
                Script(f"document.body.dispatchEvent(new CustomEvent('log_save_result', {{ detail: {{ ok: false, message: {err!r} }} }}));"),
                cls="modal-body",
                id="modal-body-content"
            )
        if parsed_log_date < today:
            err = "Log window passed, please contact your supervisor"
            return Div(
                Alert(err, variant="warning"),
                Script(f"document.body.dispatchEvent(new CustomEvent('log_save_result', {{ detail: {{ ok: false, message: {err!r} }} }}));"),
                cls="modal-body",
                id="modal-body-content"
            )

        student_profile = db.query(StudentProfile).filter(StudentProfile.user_id == current_user.id).first()
        location_enabled = bool(getattr(student_profile, "setting_location_service", True)) if student_profile else True
        if not location_enabled:
            err = "Location Services is disabled in Profile settings. Enable it to submit logs."
            return Div(
                Alert(err, variant="warning"),
                Script(f"document.body.dispatchEvent(new CustomEvent('log_save_result', {{ detail: {{ ok: false, message: {err!r} }} }}));"),
                cls="modal-body",
                id="modal-body-content"
            )

        # Validate GPS coordinates are present
        if not latitude or not longitude:
            err = "GPS location is required. Please enable location services."
            return Div(
                Alert(err, variant="danger"),
                Script(f"document.body.dispatchEvent(new CustomEvent('log_save_result', {{ detail: {{ ok: false, message: {err!r} }} }}));"),
                cls="modal-body",
                id="modal-body-content"
            )
        
        # Get active placement
        placement_repo = PlacementRepository(db)
        placement = placement_repo.get_active_placement(current_user.id)
        
        if not placement:
            err = "No active placement found. You cannot log activities."
            return Div(
                Alert(err, variant="danger"),
                Script(f"document.body.dispatchEvent(new CustomEvent('log_save_result', {{ detail: {{ ok: false, message: {err!r} }} }}));"),
                cls="modal-body",
                id="modal-body-content"
            )

        existing_day_log = db.query(DailyLog).filter(
            DailyLog.student_id == current_user.id,
            DailyLog.log_date == parsed_log_date,
        ).first()
        if existing_day_log:
            if _status_key(existing_day_log.status) == "verified":
                err = "This log has been verified and can no longer be edited."
                return Div(
                    Alert(err, variant="warning"),
                    Script(f"document.body.dispatchEvent(new CustomEvent('log_save_result', {{ detail: {{ ok: false, message: {err!r} }} }}));"),
                    cls="modal-body",
                    id="modal-body-content"
                )

            try:
                existing_day_log.activity_description = activity_description
                if latitude and longitude:
                    existing_day_log.latitude = float(latitude)
                    existing_day_log.longitude = float(longitude)

                if _status_key(existing_day_log.status) == "flagged":
                    existing_day_log.status = LogStatus.PENDING_REVIEW
                    existing_day_log.reviewer_id = None
                    existing_day_log.reviewer_comment = None
                    existing_day_log.reviewed_at = None

                if placement and placement.geofence and existing_day_log.latitude is not None and existing_day_log.longitude is not None:
                    geofence_service = GeofenceService()
                    distance, _ = geofence_service.calculate_distance_from_geofence(
                        latitude=existing_day_log.latitude,
                        longitude=existing_day_log.longitude,
                        geofence=placement.geofence,
                    )
                    existing_day_log.distance_from_geofence = distance
                    existing_day_log.location_status = geofence_service.get_location_status(
                        latitude=existing_day_log.latitude,
                        longitude=existing_day_log.longitude,
                        geofence=placement.geofence,
                    )

                db.commit()

                supervisor_id = student_profile.assigned_supervisor_id if student_profile else None
                if supervisor_id:
                    await notification_manager.send_to_user(
                        supervisor_id,
                        "log_submitted",
                        {
                            "student_id": current_user.id,
                            "student_name": current_user.full_name,
                            "log_date": parsed_log_date.isoformat(),
                            "updated": True,
                        },
                    )
                if request.headers.get("HX-Request"):
                    return hx_trigger({"log_save_result": {"ok": True, "message": "Log entry updated successfully."}})
                return RedirectResponse("/student/logbook", status_code=303)
            except Exception as e:
                db.rollback()
                err = f"Error updating log: {str(e)}"
                return Div(
                    Alert(err, variant="danger"),
                    Script(f"document.body.dispatchEvent(new CustomEvent('log_save_result', {{ detail: {{ ok: false, message: {err!r} }} }}));"),
                    cls="modal-body",
                    id="modal-body-content"
                )

        try:
            # Use SyncService for consistency (even single entry is a "sync" of 1)
            sync_service = SyncService(db)
            
            # Convert form data to expected dictionary format
            log_data = {
                "client_uuid": None, # Generated server-side if not provided
                "placement_id": placement.id,
                "log_date": parsed_log_date.isoformat(),
                "activity_description": activity_description,
                "latitude": float(latitude),
                "longitude": float(longitude),
                "skills_learned": None,
                "challenges": None
            }
            
            result = sync_service.sync_logs(current_user.id, [log_data])
            
            if result["failed"] > 0:
                raise Exception(result["errors"][0])

            student_profile = db.query(StudentProfile).filter(StudentProfile.user_id == current_user.id).first()
            supervisor_id = student_profile.assigned_supervisor_id if student_profile else None
            if supervisor_id:
                await notification_manager.send_to_user(
                    supervisor_id,
                    "log_submitted",
                    {
                        "student_id": current_user.id,
                        "student_name": current_user.full_name,
                        "log_date": parsed_log_date.isoformat(),
                    },
                )
                try:
                    notif_service = NotificationService(db)
                    notif_service.create_notification(
                        user_id=supervisor_id,
                        notification_type=NotificationType.SYSTEM_ANNOUNCEMENT,
                        title="New Log Submitted",
                        message=f"{current_user.full_name} submitted a new daily log.",
                        action_url="/supervisor/logs?filter=pending",
                    )
                    db.commit()
                except Exception:
                    db.rollback()

            if request.headers.get("HX-Request"):
                return hx_trigger({"log_save_result": {"ok": True, "message": "Log entry saved successfully."}})
            return RedirectResponse("/student/logbook", status_code=303)
            
        except Exception as e:
            err = f"Error creating log: {str(e)}"
            return Div(
                Alert(err, variant="danger"),
                Script(f"document.body.dispatchEvent(new CustomEvent('log_save_result', {{ detail: {{ ok: false, message: {err!r} }} }}));"),
                cls="modal-body",
                id="modal-body-content"
            )

    @app.post("/student/logbook/sync")
    @require_auth()
    @require_role(UserRole.STUDENT)
    async def sync_offline_entry(request: Request, db: Session = None, current_user: Optional[User] = None):
        """Sync a single offline log entry (JSON)."""
        student_profile = db.query(StudentProfile).filter(StudentProfile.user_id == current_user.id).first()
        offline_mode_enabled = bool(getattr(student_profile, "setting_offline_mode", False)) if student_profile else False
        if not offline_mode_enabled:
            return JSONResponse({"error": "Offline mode is disabled in profile settings."}, status_code=403)

        data = await request.json()
        
        # Get active placement
        placement_repo = PlacementRepository(db)
        placement = placement_repo.get_active_placement(current_user.id)
        
        if not placement:
            return JSONResponse({"error": "No active placement"}, status_code=400)
            
        try:
            log_data = {
                "client_uuid": data.get("client_uuid"),
                "placement_id": placement.id,
                "log_date": data.get("log_date"),
                "activity_description": data.get("activity_description"),
                "latitude": data.get("latitude"),
                "longitude": data.get("longitude"),
                "skills_learned": data.get("skills_learned"),
                "challenges": data.get("challenges"),
                "queued_at": data.get("queued_at"),
            }

            sync_service = SyncService(db)
            result = sync_service.sync_logs(current_user.id, [log_data])

            if result["failed"] > 0:
                return JSONResponse({"error": result["errors"]}, status_code=500)

            return JSONResponse({"status": "synced", "client_uuid": data.get("client_uuid")})
             
        except Exception as e:
            return JSONResponse({"error": str(e)}, status_code=500)
    
    @app.get("/student/logbook/filter/{filter_type}")
    @require_auth()
    @require_role(UserRole.STUDENT)
    def filter_weeks(request: Request, filter_type: str, db: Session = None, current_user: Optional[User] = None):
        """Filter weeks by type (HTMX endpoint).
        
        Args:
            request: FastHTML request object
            filter_type: Filter type (all, this_week, pending)
            db: Database session
        
        Returns:
            Filtered week cards HTML with updated filter tabs
        """
        weeks_data = _get_weeks_data(db, current_user.id, filter_type)
        
        return (
            FilterTabs(active_filter=filter_type, oob=True),
            *[
                WeekCard(
                    week["number"],
                    week["start_date"],
                    week["days"],
                    week_phase=week.get("phase", "past"),
                    show_completed_badge=bool(week.get("show_completed_badge", False)),
                )
                for week in weeks_data
            ]
        )


def _get_weeks_data(db: Session, student_id: str, filter_type: str = "all") -> List[Dict]:
    """Helper to get and format weeks data."""
    from app.domain.models.user import StudentProfile
    
    # 1. Get student profile for SIWES dates
    student_profile = db.query(StudentProfile).filter(
        StudentProfile.user_id == student_id
    ).first()
    
    if not student_profile:
        return []
    
    # 2. Get placement
    repo = PlacementRepository(db)
    placement = repo.get_active_placement(student_id)
    if not placement:
        return []
        
    start_date = student_profile.siwes_start_date
    service = LogService(db)
    
    # Calculate current week
    today = date.today()
    days_since_start = (today - start_date).days
    current_week_num = max(1, min((days_since_start // 7) + 1, 25))
    
    # 2. Get Logs
    all_logs = service.get_student_logs(student_id, placement.id)
    logs_by_date = {log.log_date: log for log in all_logs}
    
    # 3. Determine target weeks
    target_weeks = []
    
    if filter_type == "this_week":
        target_weeks = [current_week_num]
    elif filter_type == "pending":
        # Find weeks that have pending logs
        pending_weeks = set()
        for log in all_logs:
            if _status_key(log.status) == "pending_review":
                pending_weeks.add(log.week_number)
        target_weeks = sorted(list(pending_weeks))
    else: # all
        # Show weeks 1 to 25 (or up to current if preferred)
        target_weeks = range(1, 26) 

    weeks_data = []
    for week_num in target_weeks:
        if week_num < 1 or week_num > 25: continue
        
        # Calculate Monday of that week
        week_start = start_date + timedelta(weeks=week_num - 1)
        
        # Ensure week_start is Monday? 
        # Placement logic assumes start_date aligns with program start which is usually Monday.
        
        days_data = []
        
        for day_num in range(5): # Mon-Fri
            day_date = week_start + timedelta(days=day_num)
            day_log = logs_by_date.get(day_date)
            
            status = None
            hours = None
            if day_log:
                status = _status_key(day_log.status)
                # app/domain/models/log.py LogStatus enum values are strings
                hours = 8 
            
            days_data.append({
                "name": day_date.strftime("%a"),
                "display_date": day_date.strftime("%b %d"),
                "iso_date": day_date.isoformat(),
                "status": status,
                "hours": hours
            })
            
        week_phase = "past"
        if week_num == current_week_num:
            week_phase = "current"
        elif week_num > current_week_num:
            week_phase = "future"

        weeks_data.append({
            "number": week_num,
            "start_date": week_start,
            "days": days_data,
            "phase": week_phase,
            "show_completed_badge": week_num < current_week_num,
        })
        
    return weeks_data


def _calculate_current_week(db: Session, student_id: str) -> int:
    """Calculate current SIWES week from student profile start date."""
    from app.domain.models.user import StudentProfile

    student_profile = db.query(StudentProfile).filter(
        StudentProfile.user_id == student_id
    ).first()
    if not student_profile or not student_profile.siwes_start_date:
        return 1

    days_since_start = (date.today() - student_profile.siwes_start_date).days
    return max(1, min((days_since_start // 7) + 1, 25))


def _extract_initiator_id(notes: str | None) -> str | None:
    """Extract initiator metadata from call notes."""
    if not notes:
        return None
    prefix = "initiator:"
    if notes.startswith(prefix):
        return notes[len(prefix):]
    return None


def _status_key(status: object) -> str:
    """Normalize enum/string status values to lowercase string."""
    if isinstance(status, LogStatus):
        return status.value
    return str(status or "").lower()


def _location_key(location_status: object) -> str:
    """Normalize enum/string location status values to lowercase string."""
    try:
        value = getattr(location_status, "value", location_status)
        return str(value or "").lower()
    except Exception:
        return ""


def _location_proximity_score(
    distance_from_geofence: float | None,
    radius_meters: float | None,
    location_status: str,
) -> int | None:
    """Return per-log proximity score (0-100), where 100 means within geofence."""
    if location_status not in {"within", "outside"}:
        return None

    if location_status == "within":
        return 100

    if not radius_meters or radius_meters <= 0:
        return 0
    if distance_from_geofence is None:
        return 0

    # Outside-geofence decay: score falls as distance grows beyond the boundary.
    normalized = max(0.0, min(1.0, radius_meters / float(distance_from_geofence)))
    return int(round(normalized * 100))


def _calculate_missed_logs(student_profile: Optional[StudentProfile], logs: List[DailyLog]) -> int:
    """Count past working days in SIWES window that have no submitted log."""
    if not student_profile or not student_profile.siwes_start_date or not student_profile.siwes_end_date:
        return 0

    today = date.today()
    period_start = student_profile.siwes_start_date
    period_end = min(student_profile.siwes_end_date, today - timedelta(days=1))
    if period_end < period_start:
        return 0

    logged_dates = {log.log_date for log in logs}
    cursor = period_start
    missed = 0
    while cursor <= period_end:
        if cursor.weekday() < 5 and cursor not in logged_dates:
            missed += 1
        cursor += timedelta(days=1)
    return missed
