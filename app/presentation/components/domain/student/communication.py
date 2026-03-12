"""Student Communication (Chat & Calls) components."""

from fasthtml.common import *
from faststrap import Card, Button, Icon, Input, ToggleGroup
from faststrap.presets import LoadingButton, InfiniteScroll
from urllib.parse import quote


def ChatHeader(supervisor: dict) -> FT:
    """Header row for the chat interface with supervisor info and actions."""
    name = supervisor.get("name", "Dr. Ada Williams")
    dept = supervisor.get("department", "Computer Science")
    status = supervisor.get("status", "Online")
    sup_id = supervisor.get("id", "")
    
    # Generate initials
    parts = name.split()
    initials = "".join([p[0] for p in parts[:2]]) if parts else "SU"
    
    return Div(
        Div(
            # User Info
            Div(
                # Avatar with status dot
                Div(
                    Div(
                        initials,
                        cls="rounded-circle bg-primary-subtle text-primary d-flex align-items-center justify-content-center fw-bold",
                        style="width: 48px; height: 48px; font-size: 1.2rem;"
                    ),
                    Div(
                        cls=f"position-absolute {'bg-success' if status == 'Online' else 'bg-secondary'} border border-white rounded-circle",
                        style="width: 12px; height: 12px; bottom: 0; right: 0;"
                    ),
                    cls="position-relative me-3"
                ),
                Div(
                    H6(name, cls="mb-0 fw-bold"),
                    Div(dept, cls="text-muted small"),
                    Div(status, cls=f"{'text-success' if status == 'Online' else 'text-muted'} small fw-semibold"),
                    cls="d-flex flex-column"
                ),
                cls="d-flex align-items-center"
            ),
            Div(
                LoadingButton(
                    Icon("telephone"),
                    endpoint="/api/calls/create",
                    method="post",
                    target="body",
                    variant="light",
                    cls="rounded-circle me-2",
                    style="width: 40px; height: 40px;",
                    title="Start Voice Call",
                    disabled=not sup_id,
                    hx_vals=f'{{"call_type":"voice","supervisor_id":"{sup_id}"}}'
                ),
                LoadingButton(
                    Icon("camera-video"),
                    endpoint="/api/calls/create",
                    method="post",
                    target="body",
                    variant="primary",
                    cls="rounded-circle",
                    style="width: 40px; height: 40px;",
                    title="Start Video Call",
                    disabled=not sup_id,
                    hx_vals=f'{{"call_type":"video","supervisor_id":"{sup_id}"}}'
                ),
                cls="d-flex"
            ),
            cls="d-flex justify-content-between align-items-center p-3 border-bottom"
        ),
    )


def MessageBubble(text: str, time: str, is_me: bool) -> FT:
    """Individual chat message bubble."""
    
    # Styling based on sender
    if is_me:
        # User message (Right, Purple/Primary)
        align_cls = "justify-content-end"
        bubble_cls = "bg-primary text-white"
        radius_cls = "rounded-3 rounded-bottom-right-0"
    else:
        # Supervisor message (Left, Gray/Light)
        align_cls = "justify-content-start"
        bubble_cls = "bg-light text-dark"
        radius_cls = "rounded-3 rounded-bottom-left-0"
        
    return Div(
        Div(
            Div(
                text,
                cls=f"p-3 {bubble_cls} {radius_cls}",
                style="max-width: 80%; box-shadow: 0 1px 2px rgba(0,0,0,0.05);"
            ),
            Div(time, cls="text-muted small mt-1 mx-1", style="font-size: 0.7rem;"),
            cls="d-flex flex-column" + (" align-items-end" if is_me else " align-items-start")
        ),
        cls=f"d-flex {align_cls} mb-3"
    )


def ChatInput(recipient_id: str) -> FT:
    """Input area for sending messages."""
    return Form(
        Div(
            Input(type="hidden", name="recipient_id", value=recipient_id),
            Input(
                name="content",
                placeholder="Type a message...",
                cls="form-control border-0 bg-light mx-2",
                style="height: 40px;",
                autocomplete="off"
            ),
            Button(
                Icon("send-fill"),
                variant="primary",
                cls="rounded-circle text-white",
                style="width: 40px; height: 40px;",
                type="submit"
            ),
            cls="d-flex align-items-center bg-light p-2 rounded-pill border"
        ),
        cls="p-3 border-top",
        hx_post="/api/chat/send",
        hx_target="#chat-messages-list",
        hx_swap="beforeend",
        **{"hx-on::after-request": "this.reset()"}
    )


def CallHistoryItem(call: dict) -> FT:
    """Individual call history item."""
    icon_color = "text-success" if call["type"] == "incoming" else "text-primary"
    icon_name = "telephone-inbound-fill" if call["type"] == "incoming" else "telephone-outbound-fill"
    
    return Div(
        Div(
            # Call Icon
            Div(
                Icon(icon_name, cls=f"{icon_color} fs-4"),
                cls="me-3"
            ),
            # Call Details
            Div(
                H6(call["name"], cls="mb-0 fw-bold"),
                P(f"{call['type'].capitalize()} - {call['duration']}", cls="text-muted small mb-0"),
                cls="flex-grow-1"
            ),
            # Time
            P(call["time"], cls="text-muted small mb-0"),
            cls="d-flex align-items-center"
        ),
        cls="p-3 border-bottom"
    )


def CommunicationTabs(active_tab: str = "chat", supervisor_id: str = "") -> FT:
    """Communication view switcher via HTMX + ToggleGroup."""
    chat_url = "/student/communication?tab=chat"
    calls_url = "/student/communication?tab=calls"
    if supervisor_id:
        chat_url += f"&peer_id={supervisor_id}"
        calls_url += f"&peer_id={supervisor_id}"

    return ToggleGroup(
        Button(
            "Chat",
            variant="light",
            cls="comm-view-btn",
            hx_get=chat_url,
            hx_target="#student-communication-root",
            hx_push_url="true",
        ),
        Button(
            "Call History",
            variant="light",
            cls="comm-view-btn",
            hx_get=calls_url,
            hx_target="#student-communication-root",
            hx_push_url="true",
        ),
        active_index=0 if active_tab == "chat" else 1,
        cls="comm-view-toggle d-flex gap-4 mb-3 flex-wrap",
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


def CommunicationContent(
    active_tab: str = "chat",
    supervisor: dict | None = None,
    messages: list | None = None,
    recipient_id: str | None = None,
    calls: list | None = None,
    oldest_message_at: str | None = None,
    has_more_messages: bool = False,
) -> FT:
    """Communication content area (chat or call history)."""
    supervisor = supervisor or {}
    messages = messages or []
    calls = calls or []
    if active_tab == "calls":
        return Div(
            Card(
                Div(
                    H5("Call History", cls="mb-3"),
                    *[CallHistoryItem(call) for call in calls],
                    cls="p-3",
                ),
                cls="white-color",
            ),
            id="communication-content",
        )

    return Div(
        Card(
            ChatHeader(supervisor),
            Div(
                ChatHistoryLoader(recipient_id, oldest_message_at, has_more_messages),
                *[
                    MessageBubble(m["text"], m["time"], m["is_me"])
                    for m in messages
                ],
                cls="flex-grow-1 p-3 overflow-auto",
                style="height: 500px;",
                id="chat-messages-list",
            ),
            ChatInput(recipient_id),
            cls="mb-4 bg-white h-100",
            id="student-chat-content",
        ),
        id="communication-content",
    )


def CommunicationPage(
    active_tab: str = "chat",
    supervisor: dict | None = None,
    messages: list | None = None,
    calls: list | None = None,
    oldest_message_at: str | None = None,
    has_more_messages: bool = False,
) -> FT:
    """Main Communication (Chat & Calls) page."""
    if supervisor is None:
        supervisor = {}
    messages = messages or []
    calls = calls or []
        
    return Div(
        # 1. Filter Tabs
        CommunicationTabs(active_tab, supervisor.get("id", "")),
        
        # 2. Content Area (Chat or Call History)
        CommunicationContent(
            active_tab,
            supervisor,
            messages,
            supervisor.get("id"),
            calls,
            oldest_message_at=oldest_message_at,
            has_more_messages=has_more_messages,
        ),
        
        cls="communication-page pb-4"
    )


