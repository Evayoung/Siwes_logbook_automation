"""Supervisor routes."""

from datetime import date, timedelta
from fasthtml.common import *
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, desc
from app.domain.models.user import User, UserRole
from app.infrastructure.security.session import require_auth, require_role
from app.presentation.components.domain.supervisor.dashboard import SupervisorDashboard
from app.presentation.components.domain.supervisor.geofencing import GeofencingPage, GeofencingContent, PlacementFilter
from app.presentation.components.domain.supervisor.logs import StudentLogsPage, LogCard, LogFilterTabs, LogReviewPage
from app.presentation.components.ui.layouts import DashboardLayout
from app.presentation.components.ui.navigation import SupervisorSidebarNav, SupervisorBottomNav
from app.application.services.review import ReviewService
from app.domain.models.log import DailyLog, LogStatus
from app.domain.models.user import StudentProfile
from app.domain.models.placement import IndustrialPlacement
from app.domain.models.chat import ChatMessage, Notification, NotificationType
from app.domain.models.call import CallLog
from app.application.services.notifications import notification_manager
from app.application.services.notification import NotificationService


def setup_supervisor_routes(app: FastHTML):
    """Setup supervisor routes.
    
    Args:
        app: FastHTML application instance
    """
    
    @app.get("/supervisor/dashboard")
    @require_auth()
    @require_role(UserRole.SUPERVISOR)
    def supervisor_dashboard(request: Request, db: Session = None, current_user: Optional[User] = None):
        """Supervisor dashboard page.
        
        Args:
            request: FastHTML request object
            db: Database session
        
        Returns:
            Supervisor dashboard HTML
        """
        dashboard_data = _get_supervisor_dashboard_data(db, current_user.id)
        content = SupervisorDashboard(
            students_assigned=dashboard_data["students_assigned"],
            pending_review=dashboard_data["pending_review"],
            this_week_value=dashboard_data["this_week_value"],
            geofence_issues=dashboard_data["geofence_issues"],
            stale_students_count=dashboard_data["stale_students_count"],
            students=dashboard_data["students"],
        )
        
        return DashboardLayout(
            content,
            sidebar=SupervisorSidebarNav(active_page="dashboard"),
            bottom_nav=SupervisorBottomNav(active_page="dashboard"),
            current_user=current_user,
        )
    
    @app.get("/supervisor/geofencing")
    @require_auth()
    @require_role(UserRole.SUPERVISOR)
    def supervisor_geofencing(
        request: Request,
        company: str = "all",
        status: str = "all",
        db: Session = None,
        current_user: Optional[User] = None
    ):
        """Supervisor geofencing map page.
        
        Args:
            request: FastHTML request object
            db: Database session
        
        Returns:
            Geofencing map HTML
        """
        placements, companies = _get_supervisor_geofencing_data(
            db,
            current_user.id,
            company_filter=company,
            status_filter=status,
        )

        if request.headers.get("HX-Request"):
            return (
                PlacementFilter(
                    companies=companies,
                    selected_company=company,
                    selected_status=status,
                    oob=True,
                ),
                GeofencingContent(placements),
            )

        content = GeofencingPage(
            placements=placements,
            companies=companies,
            selected_company=company,
            selected_status=status,
        )
        
        return DashboardLayout(
            content,
            sidebar=SupervisorSidebarNav(active_page="geofencing"),
            bottom_nav=SupervisorBottomNav(active_page="geofencing"),
            current_user=current_user,
        )
    
    @app.get("/supervisor/logs")
    @require_auth()
    @require_role(UserRole.SUPERVISOR)
    def supervisor_logs(
        request: Request,
        filter: str = "all",
        student_id: str | None = None,
        db: Session = None,
        current_user: Optional[User] = None,
    ):
        """Supervisor student logs review page.
        
        Args:
            request: FastHTML request object
            db: Database session
        
        Returns:
            Student logs HTML
        """
        active_filter = filter if filter in {"all", "pending", "verified", "flagged"} else "all"
        logs_data = _get_supervisor_logs_data(db, current_user.id, active_filter, student_id=student_id)
        content = StudentLogsPage(logs=logs_data, active_filter=active_filter, student_id=student_id)
        
        return DashboardLayout(
            content,
            sidebar=SupervisorSidebarNav(active_page="logs"),
            bottom_nav=SupervisorBottomNav(active_page="logs"),
            current_user=current_user,
        )

    @app.get("/supervisor/logs/filter/{filter_key}")
    @require_auth()
    @require_role(UserRole.SUPERVISOR)
    def filter_logs(request: Request, filter_key: str, student_id: str | None = None, db: Session = None, current_user: Optional[User] = None):
        """Filter logs and update tabs.
        
        Args:
            request: Request object (needed for auth decorator)
            filter_key: active filter key
            db: Database session
            
        Returns:
            Updated logs and tabs
        """
        filtered_logs = _get_supervisor_logs_data(db, current_user.id, filter_key, student_id=student_id)
            
        # Return tabs (OOB swap) and log cards
        return (
            LogFilterTabs(active_filter=filter_key, oob=True, student_id=student_id),
            *[LogCard(log) for log in filtered_logs]
        )

    @app.get("/supervisor/logs/review/{log_id}")
    @require_auth()
    @require_role(UserRole.SUPERVISOR)
    def review_log(request: Request, log_id: str, db: Session = None, current_user: Optional[User] = None):
        """Show detailed review page.
        
        Args:
            request: Request object
            log_id: Log ID
            db: Database session
            
        Returns:
            Log review page HTML
        """
        log = db.query(DailyLog).filter(DailyLog.id == log_id).first()
        if not log:
            return Div(
                H1("Log Not Found"),
                P("The selected log entry does not exist."),
                A("Back to Logs", href="/supervisor/logs", cls="btn btn-primary"),
                cls="container py-5"
            )

        student_profile = db.query(StudentProfile).filter(StudentProfile.user_id == log.student_id).first()
        if not student_profile or student_profile.assigned_supervisor_id != current_user.id:
            return RedirectResponse("/unauthorized", status_code=303)

        student = db.query(User).filter(User.id == log.student_id).first()
        location_status = "Within geofence" if log.location_status and log.location_status.value == "within" else "Outside geofence"
        if log.location_status and log.location_status.value == "unknown":
            location_status = "Unknown location"

        distance = f"{(log.distance_from_geofence or 0):.0f}m"
        coords = "N/A"
        if log.latitude is not None and log.longitude is not None:
            coords = f"{log.latitude:.6f}, {log.longitude:.6f}"

        review_status = "pending"
        if log.status == LogStatus.VERIFIED:
            review_status = "verified"
        elif log.status == LogStatus.FLAGGED:
            review_status = "flagged"

        log_data = {
            "student": {
                "name": student.full_name if student else "Unknown Student",
                "matric": student_profile.matriculation_number,
                "company": student_profile.institution,
            },
            "log": {
                "week": log.week_number,
                "date": log.log_date.isoformat(),
                "description": log.activity_description,
                "hours": "8h",
                "day": log.log_date.strftime("%A"),
                "status": review_status,
                "review_comment": log.reviewer_comment,
            },
            "location": {
                "status": location_status,
                "coords": coords,
                "distance": distance,
                "radius_text": "Based on configured placement geofence",
            },
        }
        return LogReviewPage(log_id, log_data)

    @app.post("/supervisor/logs/review/{log_id}")
    @require_auth()
    @require_role(UserRole.SUPERVISOR)
    async def save_review(request: Request, log_id: str, db: Session = None, current_user: Optional[User] = None):
        """Save a single log review decision."""
        log = db.query(DailyLog).filter(DailyLog.id == log_id).first()
        if not log:
            return RedirectResponse("/supervisor/logs", status_code=303)

        student_profile = db.query(StudentProfile).filter(StudentProfile.user_id == log.student_id).first()
        if not student_profile or student_profile.assigned_supervisor_id != current_user.id:
            return RedirectResponse("/unauthorized", status_code=303)

        form = await request.form()
        review_status = (form.get("review_status") or "pending").lower()
        review_comment = form.get("review_comment")
        review_service = ReviewService(db)
        student_id = log.student_id

        try:
            if review_status == "verified":
                review_service.verify_log(log_id, current_user.id, review_comment)
                notif_type = NotificationType.LOG_VERIFIED
                notif_title = "Log Verified"
                notif_msg = "Your log entry has been verified."
            elif review_status == "flagged":
                review_service.flag_log(log_id, current_user.id, review_comment or "Flagged by supervisor")
                notif_type = NotificationType.LOG_FLAGGED
                notif_title = "Log Flagged"
                notif_msg = review_comment or "Your log entry was flagged by your supervisor."
            else:
                review_service.unflag_log(log_id, current_user.id)
                notif_type = NotificationType.LOG_REVIEWED
                notif_title = "Log Returned To Pending"
                notif_msg = "Your log entry is pending review again."
            db.commit()

            await notification_manager.send_to_user(
                student_id,
                "log_reviewed",
                {
                    "log_id": log_id,
                    "status": review_status,
                    "message": notif_msg,
                },
            )

            try:
                notif_service = NotificationService(db)
                notif_service.create_notification(
                    user_id=student_id,
                    notification_type=notif_type,
                    title=notif_title,
                    message=notif_msg,
                    related_log_id=log_id,
                    action_url="/student/logbook",
                )
                db.commit()
            except Exception:
                db.rollback()
        except Exception:
            db.rollback()

        return RedirectResponse("/supervisor/logs", status_code=303)

    @app.post("/supervisor/logs/verify-selected")
    @require_auth()
    @require_role(UserRole.SUPERVISOR)
    async def verify_selected_logs(request: Request, db: Session = None, current_user: Optional[User] = None):
        """Bulk-verify selected logs via HTMX form submission."""
        form = await request.form()
        selected_logs = [log_id for log_id in form.getlist("selected_logs") if log_id]
        feedback = form.get("review_comment")

        if not selected_logs:
            return Div(
                "Select at least one log to verify.",
                cls="alert alert-warning mb-3",
                id="logs-feedback"
            )

        logs = db.query(DailyLog).filter(DailyLog.id.in_(selected_logs)).all()
        if not logs:
            return Div(
                "Selected logs were not found.",
                cls="alert alert-warning mb-3",
                id="logs-feedback"
            )

        review_service = ReviewService(db)
        verified = 0
        failed = 0
        unauthorized = 0
        errors = []

        for log in logs:
            student_profile = db.query(StudentProfile).filter(
                StudentProfile.user_id == log.student_id
            ).first()

            if not student_profile or student_profile.assigned_supervisor_id != current_user.id:
                unauthorized += 1
                continue

            try:
                result = review_service.verify_log(log.id, current_user.id, feedback)
                if result:
                    verified += 1
                    await notification_manager.send_to_user(
                        log.student_id,
                        "log_reviewed",
                        {
                            "log_id": log.id,
                            "status": "verified",
                            "message": "Your log entry has been verified.",
                        },
                    )
                    try:
                        notif_service = NotificationService(db)
                        notif_service.create_notification(
                            user_id=log.student_id,
                            notification_type=NotificationType.LOG_VERIFIED,
                            title="Log Verified",
                            message="Your log entry has been verified.",
                            related_log_id=log.id,
                            action_url="/student/logbook",
                        )
                    except Exception:
                        pass
                else:
                    failed += 1
                    errors.append(f"{log.id}: log not found")
            except Exception as e:
                failed += 1
                errors.append(f"{log.id}: {str(e)}")

        try:
            if verified > 0:
                db.commit()
            else:
                db.rollback()
        except Exception as e:
            db.rollback()
            return Div(
                f"Failed to save verification changes: {str(e)}",
                cls="alert alert-danger mb-3",
                id="logs-feedback"
            )

        summary = f"Verified: {verified}"
        if failed:
            summary += f", Failed: {failed}"
        if unauthorized:
            summary += f", Unauthorized: {unauthorized}"
        if errors:
            summary += f". Issues: {'; '.join(errors[:2])}"

        variant = "success" if verified > 0 and failed == 0 and unauthorized == 0 else "warning"
        return Div(
            summary,
            cls=f"alert alert-{variant} mb-3",
            id="logs-feedback"
        )
        
    @app.get("/supervisor/communication")
    @require_auth()
    @require_role(UserRole.SUPERVISOR)
    def supervisor_communication(
        request: Request,
        tab: str = "chat",
        student_search: str = "",
        db: Session = None,
        current_user: Optional[User] = None,
    ):
        """Supervisor communication page.
        
        Args:
            request: FastHTML request object
            tab: Active tab (chat or calls)
            db: Database session
        
        Returns:
            Communication HTML
        """
        tab = "calls" if tab == "calls" else "chat"
        from app.presentation.components.domain.supervisor.communication import SupervisorCommunicationPage
        from app.domain.models.user import User
        search_value = (student_search or "").strip()
        search_key = search_value.lower()
        
        # Fetch assigned students
        assigned_profiles = db.query(StudentProfile).filter(
            StudentProfile.assigned_supervisor_id == current_user.id
        ).all()
        
        students_data = []
        active_users = set(notification_manager.get_active_users())
        unread_rows = db.query(ChatMessage).filter(
            ChatMessage.receiver_id == current_user.id,
            ChatMessage.is_read == False,
        ).all()
        unread_by_sender: dict[str, int] = {}
        for row in unread_rows:
            unread_by_sender[row.sender_id] = unread_by_sender.get(row.sender_id, 0) + 1

        for profile in assigned_profiles:
            # Get user details
            student_user = db.query(User).filter(User.id == profile.user_id).first()
            if student_user:
                if search_key:
                    haystack = " ".join(
                        [
                            str(student_user.full_name or ""),
                            str(profile.matriculation_number or ""),
                            str(profile.institution or ""),
                        ]
                    ).lower()
                    if search_key not in haystack:
                        continue

                 # Generate initials
                parts = student_user.full_name.split()
                initials = "".join([p[0] for p in parts[:2]]) if parts else "ST"
                
                # Mock color/unread (could be added to model later)
                colors = ["#6366f1", "#a855f7", "#6b7280", "#ef4444", "#10b981"]
                # Use hash of ID to pick consistent color
                color_idx = hash(student_user.id) % len(colors)
                
                students_data.append({
                    "id": student_user.id,
                    "name": student_user.full_name,
                    "initials": initials,
                    "matric": profile.matriculation_number,
                    "company": profile.institution or "Univ", # Should be placement company?
                    "color": colors[color_idx],
                    "unread": unread_by_sender.get(student_user.id, 0),
                    "status": "Online" if student_user.id in active_users else "Offline",
                })
        
        # Handle active student
        active_student_id = request.query_params.get("student_id")
        current_student = None
        
        if active_student_id and students_data:
            current_student = next((s for s in students_data if s["id"] == active_student_id), None)
            
        if not current_student and students_data:
            current_student = students_data[0]
            
        # Fallback if no students assigned
        if not current_student:
             current_student = {
                 "id": "", 
                 "name": "No Students Assigned", 
                 "initials": "--", 
                 "company": "", 
                 "color": "#9ca3af",
                 "unread": 0
             }

        messages = []
        has_more_messages = False
        oldest_message_at = None
        if current_student and current_student.get("id"):
            # Mark incoming messages in selected conversation as read.
            db.query(ChatMessage).filter(
                ChatMessage.sender_id == current_student["id"],
                ChatMessage.receiver_id == current_user.id,
                ChatMessage.is_read == False,
            ).update({"is_read": True}, synchronize_session=False)
            db.query(Notification).filter(
                Notification.user_id == current_user.id,
                Notification.type == NotificationType.MESSAGE_RECEIVED,
                Notification.is_read == False,
                Notification.action_url.like(f"%peer_id={current_student['id']}%"),
            ).update({"is_read": True}, synchronize_session=False)
            db.commit()

            page_size = 20
            chat_logs_desc = db.query(ChatMessage).filter(
                or_(
                    and_(ChatMessage.sender_id == current_user.id, ChatMessage.receiver_id == current_student["id"]),
                    and_(ChatMessage.sender_id == current_student["id"], ChatMessage.receiver_id == current_user.id)
                )
            ).order_by(desc(ChatMessage.created_at)).limit(page_size + 1).all()
            has_more_messages = len(chat_logs_desc) > page_size
            visible_logs = list(reversed(chat_logs_desc[:page_size]))
            if visible_logs:
                oldest_message_at = visible_logs[0].created_at.isoformat()
            messages = [
                {
                    "sender": "me" if m.sender_id == current_user.id else "them",
                    "text": m.message_body,
                    "time": m.created_at.strftime("%I:%M %p"),
                }
                for m in visible_logs
            ]

        calls = []
        if students_data:
            student_ids = [s["id"] for s in students_data if s.get("id")]
            call_logs = db.query(CallLog).filter(
                CallLog.supervisor_id == current_user.id,
                CallLog.student_id.in_(student_ids)
            ).order_by(CallLog.started_at.desc()).limit(50).all()

            student_name_by_id = {s["id"]: s["name"] for s in students_data}
            for c in call_logs:
                duration = "Missed" if c.status in {"declined", "missed"} else f"{(c.duration_minutes or 0)} min"
                calls.append(
                    {
                        "student": student_name_by_id.get(c.student_id, "Unknown Student"),
                        "date": c.started_at.strftime("%b %d, %Y - %I:%M %p"),
                        "duration": duration,
                        "type": "Video" if c.call_type == "video" else "Voice",
                        "status": c.status.capitalize(),
                        "student_id": c.student_id,
                    }
                )

        if tab == "calls":
            db.query(Notification).filter(
                Notification.user_id == current_user.id,
                Notification.is_read == False,
                Notification.action_url.like("%/supervisor/communication?tab=calls%"),
            ).update({"is_read": True}, synchronize_session=False)
            db.commit()

        body = Div(
            SupervisorCommunicationPage(
            active_tab=tab, 
            students=students_data, 
            current_student=current_student,
            messages=messages,
            calls=calls,
            oldest_message_at=oldest_message_at,
            has_more_messages=has_more_messages,
            search_query=search_value,
            ),
            id="supervisor-communication-root",
        )

        if request.headers.get("HX-Request"):
            return body

        return DashboardLayout(
            body,
            sidebar=SupervisorSidebarNav(active_page="communication"),
            bottom_nav=SupervisorBottomNav(active_page="communication"),
            current_user=current_user,
        )


def _status_label(status: LogStatus) -> str:
    """Map enum status to UI label."""
    if status == LogStatus.VERIFIED:
        return "Verified"
    if status == LogStatus.FLAGGED:
        return "Flagged"
    return "Pending"


def _get_supervisor_logs_data(
    db: Session,
    supervisor_id: str,
    filter_key: str = "all",
    student_id: str | None = None,
) -> list[dict]:
    """Fetch logs for students assigned to the supervisor and map for UI."""
    assigned_profiles = db.query(StudentProfile).filter(
        StudentProfile.assigned_supervisor_id == supervisor_id
    ).all()
    if not assigned_profiles:
        return []

    student_ids = [p.user_id for p in assigned_profiles]
    profile_by_student = {p.user_id: p for p in assigned_profiles}

    query = db.query(DailyLog).filter(DailyLog.student_id.in_(student_ids))
    if student_id:
        query = query.filter(DailyLog.student_id == student_id)
    if filter_key == "pending":
        query = query.filter(DailyLog.status == LogStatus.PENDING_REVIEW)
    elif filter_key == "verified":
        query = query.filter(DailyLog.status == LogStatus.VERIFIED)
    elif filter_key == "flagged":
        query = query.filter(DailyLog.status == LogStatus.FLAGGED)

    logs = query.order_by(DailyLog.log_date.desc()).all()
    if not logs:
        return []

    user_ids = list({log.student_id for log in logs})
    users = db.query(User).filter(User.id.in_(user_ids)).all()
    user_by_id = {u.id: u for u in users}

    logs_data = []
    for log in logs:
        student = user_by_id.get(log.student_id)
        profile = profile_by_student.get(log.student_id)
        logs_data.append(
            {
                "id": log.id,
                "student_name": student.full_name if student else "Unknown Student",
                "matric": profile.matriculation_number if profile else "--",
                "week": log.week_number,
                "date": log.log_date.isoformat(),
                "description": log.activity_description,
                "status": _status_label(log.status),
                "geofence_status": log.location_status.value if log.location_status else "unknown",
            }
        )

    return logs_data


def _get_supervisor_dashboard_data(db: Session, supervisor_id: str) -> dict:
    """Build live dashboard metrics for supervisor."""
    assigned_profiles = db.query(StudentProfile).filter(
        StudentProfile.assigned_supervisor_id == supervisor_id
    ).all()
    if not assigned_profiles:
        return {
            "students_assigned": 0,
            "pending_review": 0,
            "this_week_value": "0/0",
            "geofence_issues": 0,
            "stale_students_count": 0,
            "students": [],
        }

    student_ids = [p.user_id for p in assigned_profiles]
    profile_by_student = {p.user_id: p for p in assigned_profiles}
    users = db.query(User).filter(User.id.in_(student_ids)).all()
    user_by_id = {u.id: u for u in users}

    logs = db.query(DailyLog).filter(DailyLog.student_id.in_(student_ids)).all()
    pending_review = sum(1 for l in logs if l.status == LogStatus.PENDING_REVIEW)
    geofence_issues = sum(1 for l in logs if getattr(l.location_status, "value", None) == "outside")

    today = date.today()
    week_start = today - timedelta(days=today.weekday())
    week_end = week_start + timedelta(days=4)
    week_days_elapsed = min(max((today - week_start).days + 1, 0), 5)
    expected_this_week = len(student_ids) * week_days_elapsed
    this_week_logs = sum(1 for l in logs if l.log_date and week_start <= l.log_date <= week_end)
    this_week_value = f"{this_week_logs}/{expected_this_week}"

    by_student: dict[str, dict] = {}
    for sid in student_ids:
        by_student[sid] = {
            "verified": 0,
            "pending": 0,
            "flagged": 0,
            "latest_log_date": None,
            "latest_week": None,
        }

    for log in logs:
        entry = by_student.get(log.student_id)
        if not entry:
            continue
        if log.status == LogStatus.VERIFIED:
            entry["verified"] += 1
        elif log.status == LogStatus.FLAGGED:
            entry["flagged"] += 1
        else:
            entry["pending"] += 1
        if log.log_date and (entry["latest_log_date"] is None or log.log_date > entry["latest_log_date"]):
            entry["latest_log_date"] = log.log_date
            entry["latest_week"] = log.week_number

    stale_cutoff = today - timedelta(days=3)
    stale_students_count = 0
    students = []
    for sid in student_ids:
        user = user_by_id.get(sid)
        profile = profile_by_student.get(sid)
        stats = by_student[sid]
        full_name = user.full_name if user else "Unknown Student"
        name_parts = [p for p in full_name.split() if p]
        initials = "".join(p[0] for p in name_parts[:2]).upper() if name_parts else "--"
        latest_date = stats["latest_log_date"]
        if latest_date is None or latest_date < stale_cutoff:
            stale_students_count += 1
        students.append(
            {
                "id": sid,
                "name": full_name,
                "matric": profile.matriculation_number if profile else "--",
                "initials": initials,
                "last_log": latest_date.strftime("%b %d, %Y") if latest_date else "No log yet",
                "week": f"Week {stats['latest_week']}" if stats["latest_week"] else "-",
                "verified": stats["verified"],
                "pending": stats["pending"],
                "flagged": stats["flagged"],
            }
        )

    students.sort(key=lambda s: s["name"])
    return {
        "students_assigned": len(student_ids),
        "pending_review": pending_review,
        "this_week_value": this_week_value,
        "geofence_issues": geofence_issues,
        "stale_students_count": stale_students_count,
        "students": students,
    }


def _format_last_checkin(last_log_date: date | None) -> str:
    """Format last check-in date as relative text."""
    if not last_log_date:
        return "No check-in yet"

    days_old = (date.today() - last_log_date).days
    if days_old <= 0:
        return "Today"
    if days_old == 1:
        return "1 day ago"
    if days_old < 7:
        return f"{days_old} days ago"
    return last_log_date.isoformat()


def _get_supervisor_geofencing_data(
    db: Session,
    supervisor_id: str,
    company_filter: str = "all",
    status_filter: str = "all"
) -> tuple[list[dict], list[str]]:
    """Build geofencing view data from assigned students, placements, and logs."""
    assigned_profiles = db.query(StudentProfile).filter(
        StudentProfile.assigned_supervisor_id == supervisor_id
    ).all()
    if not assigned_profiles:
        return [], []

    student_ids = [p.user_id for p in assigned_profiles]
    users = db.query(User).filter(User.id.in_(student_ids)).all()
    user_by_id = {u.id: u for u in users}

    all_logs = db.query(DailyLog).filter(DailyLog.student_id.in_(student_ids)).all()
    profile_placement_ids = {p.placement_id for p in assigned_profiles if p.placement_id}
    log_placement_ids = {l.placement_id for l in all_logs if l.placement_id}
    placement_ids = sorted(profile_placement_ids.union(log_placement_ids))
    if not placement_ids:
        return [], []

    placements = db.query(IndustrialPlacement).filter(
        IndustrialPlacement.id.in_(placement_ids)
    ).all()
    placement_by_id = {p.id: p for p in placements}
    companies = sorted({p.company_name for p in placements if p.company_name})

    latest_log_by_student: dict[str, DailyLog] = {}
    for log in all_logs:
        existing = latest_log_by_student.get(log.student_id)
        if not existing:
            latest_log_by_student[log.student_id] = log
            continue
        if existing.log_date is None and log.log_date is not None:
            latest_log_by_student[log.student_id] = log
            continue
        if log.log_date and existing.log_date and log.log_date > existing.log_date:
            latest_log_by_student[log.student_id] = log

    placement_students: dict[str, set[str]] = {}
    for profile in assigned_profiles:
        if profile.placement_id:
            placement_students.setdefault(profile.placement_id, set()).add(profile.user_id)
    for log in all_logs:
        if log.placement_id:
            placement_students.setdefault(log.placement_id, set()).add(log.student_id)

    placements_data: list[dict] = []
    recent_cutoff = date.today() - timedelta(days=7)

    for placement_id in placement_ids:
        placement = placement_by_id.get(placement_id)
        if not placement:
            continue

        site_student_ids = sorted(list(placement_students.get(placement_id, set())))
        student_names: list[str] = []
        last_dates: list[date] = []
        active_students = 0

        for sid in site_student_ids:
            student = user_by_id.get(sid)
            if student:
                student_names.append(student.full_name)

            latest = latest_log_by_student.get(sid)
            if latest and latest.log_date:
                last_dates.append(latest.log_date)
                if latest.log_date >= recent_cutoff:
                    active_students += 1

        last_log_date = max(last_dates) if last_dates else None
        status_key = "active" if active_students > 0 else "inactive"

        geofence = placement.geofence
        coords = "Coordinates not set"
        radius_text = "Geofence not configured"
        if geofence:
            coords = f"{geofence.latitude:.6f}, {geofence.longitude:.6f}"
            radius_text = f"Geofence radius: {geofence.radius_meters}m"

        site = {
            "placement_id": placement.id,
            "company": placement.company_name,
            "address": placement.address,
            "coords": coords,
            "status_key": status_key,
            "students": sorted(student_names),
            "students_count": len(site_student_ids),
            "last_checkin": _format_last_checkin(last_log_date),
            "radius_text": radius_text,
        }

        if company_filter != "all" and site["company"] != company_filter:
            continue
        if status_filter != "all" and site["status_key"] != status_filter:
            continue
        placements_data.append(site)

    placements_data.sort(key=lambda s: (s["status_key"] != "active", s["company"]))
    return placements_data, companies
