"""Call notification modal component."""

from fasthtml.common import *
from faststrap import Card, Button, Icon


def CallNotificationModal() -> FT:
    """Modal that appears when receiving an incoming call.
    
    This modal is hidden by default and shown via JavaScript when
    an SSE 'call_incoming' event is received.
    
    Returns:
        Modal component with call details and Accept/Decline buttons
    """
    return Div(
        # Backdrop
        Div(
            id="call-notification-backdrop",
            cls="modal-backdrop fade",
            style="display: none;"
        ),
        
        # Modal
        Div(
            Div(
                Div(
                    # Header
                    Div(
                        H5("Incoming Call", cls="modal-title fw-bold"),
                        cls="modal-header border-0 pb-0"
                    ),
                    
                    # Body
                    Div(
                        # Caller Avatar
                        Div(
                            Div(
                                id="caller-initials",
                                cls="rounded-circle bg-primary text-white d-flex align-items-center justify-content-center fw-bold mx-auto mb-3",
                                style="width: 80px; height: 80px; font-size: 2rem;"
                            ),
                            cls="text-center"
                        ),
                        
                        # Caller Name
                        H4(
                            id="caller-name",
                            cls="text-center mb-2"
                        ),
                        
                        # Call Type
                        P(
                            Icon("camera-video", cls="me-2"),
                            Span(id="call-type-text"),
                            cls="text-center text-muted"
                        ),
                        
                        # Ringing Animation
                        Div(
                            Div(cls="spinner-grow spinner-grow-sm text-primary me-2"),
                            "Ringing...",
                            cls="text-center text-muted small mt-3",
                            id="ringing-indicator"
                        ),
                        
                        cls="modal-body text-center py-4"
                    ),
                    
                    # Footer with Action Buttons
                    Div(
                        Button(
                            Icon("telephone-x", cls="me-2"),
                            "Decline",
                            variant="light",
                            cls="btn-lg px-4",
                            id="decline-call-btn"
                        ),
                        Button(
                            Icon("telephone-fill", cls="me-2"),
                            "Accept",
                            variant="success",
                            cls="btn-lg px-4",
                            id="accept-call-btn"
                        ),
                        cls="modal-footer border-0 justify-content-center gap-3"
                    ),
                    
                    cls="modal-content shadow-lg"
                ),
                cls="modal-dialog modal-dialog-centered"
            ),
            id="call-notification-modal",
            cls="modal fade",
            tabindex="-1",
            style="display: none;",
            **{"aria-hidden": "true"}
        )
    )
