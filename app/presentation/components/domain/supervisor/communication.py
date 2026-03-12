"""Supervisor communication components."""

from fasthtml.common import *
from faststrap import Card, Button, Icon, Row, Col, Table, THead, TBody, TRow, TCell, Input, ToggleGroup
from faststrap.presets import LoadingButton, InfiniteScroll
from urllib.parse import quote


def ChatSidebar(
    students: list,
    active_id: str,
    active_tab: str = "chat",
    search_query: str = "",
) -> FT:
    """Sidebar list of students for chat."""
    student_items = []
    for s in students:
        is_active = s["id"] == active_id
        active_cls = "bg-light" if is_active else "bg-white"
        avatar = Div(
            s["initials"],
            cls="rounded-circle d-flex align-items-center justify-content-center fw-bold me-3 text-white",
            style=f"width: 40px; height: 40px; min-width: 40px; background-color: {s['color']};",
        )
        details = Div(
            Div(
                H6(s["name"], cls="mb-0 fw-bold text-start"),
                Span(s["unread"], cls="badge bg-primary rounded-pill ms-auto") if s.get("unread") else "",
                cls="d-flex w-100 justify-content-between align-items-center",
            ),
            P(s["company"], cls="text-muted small mb-0 text-start text-truncate"),
            cls="flex-grow-1 overflow-hidden",
        )
        item = Button(
            Div(avatar, details, cls="d-flex align-items-center w-100"),
            variant="light",
            cls=f"w-100 border-0 p-3 mb-1 {active_cls}",
            hx_get=f"/supervisor/communication?tab={active_tab}&student_id={s['id']}",
            hx_target="#supervisor-communication-root",
            hx_push_url="true",
        )
        student_items.append(item)

    search_url = f"/supervisor/communication?tab={active_tab}"
    if active_id:
        search_url += f"&student_id={active_id}"

    return Card(
        Div(
            Input(
                "student_search",
                input_type="search",
                placeholder="Search students...",
                value=search_query,
                cls="form-control bg-light border-0",
                hx_get=search_url,
                hx_target="#supervisor-communication-root",
                hx_trigger="keyup changed delay:300ms, search",
                hx_push_url="true",
            ),
            cls="mb-3",
        ),
        Div(*student_items, cls="d-flex flex-column"),
        cls="mb-4 bg-white",
    )


def ChatMessage(msg: dict) -> FT:
    """Individual chat message bubble."""
    is_me = msg["sender"] == "me"
    bubble_cls = "bg-primary text-white" if is_me else "bg-light text-dark"
    align_cls = "align-items-end" if is_me else "align-items-start"
    justify_cls = "justify-content-end" if is_me else "justify-content-start"
    return Div(
        Div(
            Div(msg["text"], cls=f"p-3 rounded-3 {bubble_cls}"),
            P(msg["time"], cls="small text-muted mt-1 mb-0"),
            cls=f"d-flex flex-column {align_cls} mb-3",
            style="max-width: 80%;",
        ),
        cls=f"d-flex {justify_cls}",
    )


def ChatHistoryLoader(recipient_id: str | None, oldest_message_at: str | None, has_more_messages: bool) -> FT:
    """Top-of-list loader for older chat history pages."""
    if not recipient_id:
        return Div(id="chat-history-sentinel")

    if has_more_messages and oldest_message_at:
        before = quote(oldest_message_at, safe="")
        return InfiniteScroll(
            endpoint=f"/api/chat/history/{recipient_id}/older?before={before}&limit=20",
            target="this",
            trigger="intersect once root:#chat-messages-list threshold:0.01",
            hx_swap="outerHTML",
            id="chat-history-sentinel",
            content=Div("Loading older messages...", cls="small text-muted text-center py-1"),
        )

    return Div("Start of conversation", id="chat-history-sentinel", cls="small text-muted text-center py-1")


def ChatMainArea(student: dict, messages: list, oldest_message_at: str | None = None, has_more_messages: bool = False) -> FT:
    """Main chat area with header, messages, and input."""
    student_id = student.get("id", "")
    student_status = student.get("status", "Offline")
    return Card(
        Div(
            Div(
                Div(
                    Div(
                        student["initials"],
                        cls="rounded-circle d-flex align-items-center justify-content-center fw-bold me-3 text-white",
                        style=f"width: 40px; height: 40px; background-color: {student['color']};",
                    ),
                    Div(
                        H6(student["name"], cls="mb-0 fw-bold"),
                        Div(
                            Div(
                                cls=f"{'bg-success' if student_status == 'Online' else 'bg-secondary'} rounded-circle me-1",
                                style="width: 8px; height: 8px;",
                            ),
                            student_status,
                            cls="small text-muted d-flex align-items-center",
                        ),
                    ),
                    cls="d-flex align-items-center",
                ),
                Div(
                    LoadingButton(
                        Icon("telephone"),
                        endpoint="/api/calls/create",
                        method="post",
                        target="body",
                        variant="light",
                        cls="rounded-circle me-2",
                        title="Start Voice Call",
                        disabled=not student_id,
                        hx_vals=f'{{"call_type":"voice","student_id":"{student_id}"}}',
                    ),
                    LoadingButton(
                        Icon("camera-video"),
                        endpoint="/api/calls/create",
                        method="post",
                        target="body",
                        variant="primary",
                        cls="rounded-circle text-white",
                        title="Start Video Call",
                        disabled=not student_id,
                        hx_vals=f'{{"call_type":"video","student_id":"{student_id}"}}',
                    ),
                ),
                cls="d-flex justify-content-between align-items-center p-3 border-bottom",
            ),
        ),
        Div(
            ChatHistoryLoader(student_id, oldest_message_at, has_more_messages),
            *[ChatMessage(m) for m in messages],
            cls="flex-grow-1 p-3 overflow-auto",
            style="height: 500px;",
            id="chat-messages-list",
        ),
        Div(
            Form(
                Div(
                    Input(type="hidden", name="recipient_id", value=student_id),
                    Input(name="content", input_type="text", placeholder="Type a message...", cls="form-control border-0 bg-light mx-2"),
                    Button(Icon("send"), variant="primary", cls="rounded-circle text-white", style="width: 40px; height: 40px;", type="submit"),
                    cls="d-flex align-items-center bg-light p-2 rounded-pill border",
                ),
                cls="p-3 border-top",
                hx_post="/api/chat/send",
                hx_target="#chat-messages-list",
                hx_swap="beforeend",
                **{"hx-on::after-request": "this.reset()"},
            )
        ),
        cls="mb-4 bg-white h-100",
        id="chat-main-area",
    )


def CallHistoryTable(calls: list | None = None) -> FT:
    """Table of call history."""
    calls = calls or []
    return Card(
        Div(
            Table(
                THead(
                    TRow(
                        TCell("Student", cls="text-muted small border-0", style="min-width: 150px;"),
                        TCell("Date", cls="text-muted small border-0", style="min-width: 150px;"),
                        TCell("Duration", cls="text-muted small border-0"),
                        TCell("Type", cls="text-muted small border-0", style="min-width: 120px;"),
                        TCell("Actions", cls="text-muted small border-0 text-end pe-4", style="min-width: 100px;"),
                    )
                ),
                
                TBody(
                    *[
                        TRow(
                            TCell(c["student"], cls="bg-white"),
                            TCell(c["date"], cls="align-middle text-muted bg-white"),
                            TCell(c["duration"], cls=f"align-middle {'text-danger' if c['status'].lower() in {'missed', 'declined'} else 'text-success'} bg-white"),
                            TCell(
                                Div(
                                    Icon("camera-video" if c["type"] == "Video" else "telephone", cls="me-2"),
                                    c["type"],
                                    cls=f"d-flex align-items-center {'text-primary' if c['type'] == 'Video' else 'text-muted'}",
                                ),
                                cls="align-middle bg-white",
                            ),
                            TCell(
                                LoadingButton(
                                    "Call Back",
                                    endpoint="/api/calls/create",
                                    method="post",
                                    target="body",
                                    variant="light",
                                    cls="border",
                                    hx_vals='{"call_type":"%s","student_id":"%s"}'
                                    % (c["type"].lower(), c["student_id"]),
                                    style="min-width: 100px;",
                                ),
                                cls="align-middle text-end pe-4 bg-white",
                            ),
                        )
                        for c in calls
                    ]
                ),
                cls="table-hover align-middle",
                responsive=True,
            ),
            cls="table-responsive",
        ),
        cls="mb-4 bg-white",
    )


def SupervisorCommunicationPage(
    active_tab: str = "chat",
    students: list | None = None,
    current_student: dict | None = None,
    messages: list | None = None,
    calls: list | None = None,
    oldest_message_at: str | None = None,
    has_more_messages: bool = False,
    search_query: str = "",
) -> FT:
    """Main supervisor communication page."""
    students = students or []
    messages = messages or []
    calls = calls or []

    if not current_student and students:
        current_student = students[0]

    if not current_student:
        current_student = {"id": "", "name": "No Student Selected", "initials": "--", "color": "#ccc", "status": "Offline"}

    active_student_id = current_student.get("id", "")
    chat_url = "/supervisor/communication?tab=chat"
    calls_url = "/supervisor/communication?tab=calls"
    if active_student_id:
        chat_url += f"&student_id={active_student_id}"
        calls_url += f"&student_id={active_student_id}"

    tabs = ToggleGroup(
        Button(
            "Chat",
            variant="light",
            cls="comm-view-btn",
            hx_get=chat_url,
            hx_target="#supervisor-communication-root",
            hx_push_url="true",
        ),
        Button(
            "Call History",
            variant="light",
            cls="comm-view-btn",
            hx_get=calls_url,
            hx_target="#supervisor-communication-root",
            hx_push_url="true",
        ),
        active_index=0 if active_tab == "chat" else 1,
        cls="comm-view-toggle d-flex gap-4 mb-4 flex-wrap",
    )

    content = (
        Row(
            Col(
                ChatSidebar(
                    students,
                    active_id=current_student["id"],
                    active_tab=active_tab,
                    search_query=search_query,
                ),
                xs=12,
                md=4,
                cls="mb-4",
            ),
            Col(ChatMainArea(current_student, messages, oldest_message_at, has_more_messages), xs=12, md=8),
        )
        if active_tab == "chat"
        else CallHistoryTable(calls)
    )

    return Div(
        Div(
            H2("Chat & Call Logs", cls="mb-0"),
            P("Communicate with your assigned students", cls="text-muted"),
            cls="mb-4",
        ),
        tabs,
        content,
        cls="communication-page pb-4",
    )
