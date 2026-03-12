"""Authentication components for login and registration."""

from fasthtml.common import *
from faststrap import Input, Checkbox, Button, Alert, Icon
from app.presentation.components.ui.layouts import AuthLayout


def LoginForm(error: str | None = None) -> FT:
    """Login form component.
    
    Args:
        error: Optional error message to display
    
    Returns:
        Form element with email and password fields
    """
    return Form(
        # Error alert
        Alert(error, variant="danger", dismissible=True) if error else None,
        
        # Email field
        Input(
            "email",
            label="Email Address",
            input_type="email",
            placeholder="student@university.edu",
            required=True,
            autofocus=True,
            cls="w-100"
        ),
        
        # Password field
        Input(
            "password",
            label="Password",
            input_type="password",
            placeholder="Enter your password",
            required=True,
            cls="w-100"
        ),
        
        # Remember me and Forgot password in same row
        Div(
            Checkbox("remember_me", label="Remember me"),

            cls="d-flex justify-content-between align-items-center mb-3 flex-wrap"
        ),

        
        # Submit button
        Button("Login", variant="primary", full_width=True, type="submit"),
        Div(
            P(
                "Offline password login is not available. If you logged in recently, you can continue using cached workspace offline.",
                cls="text-muted small text-center mt-2 mb-1",
                id="login-offline-hint",
            ),
            A(
                "Forgot password? Contact admin",
                href="mailto:meshelleva@gmail.com?subject=SIWES%20Password%20Reset",
                cls="text-decoration-none d-block text-center small",
            ),
        ),
        
        method="post",
        action="/login",
        cls="mx-auto",
        style="max-width: 400px;"
    )


def LoginPage(error: str | None = None) -> FT:
    """Complete login page.
    
    Args:
        error: Optional error message
    
    Returns:
        Full login page with AuthLayout
    """
    return AuthLayout(
        Div(
            Div(
                Icon("mortarboard-fill", style="font-size: 2.5rem;"), 
                cls="text-center text-white d-flex justify-content-center align-items-center",
                style="background-color: var(--bs-primary); border-radius: 10px; width: 60px; height: 60px;"
            ),
            cls="mb-4 d-flex justify-content-center align-items-center w-100",
        ),
        H1("SIWES Portal", cls="text-center mb-2"),
        P("Sign in to your account", cls="text-center text-muted mb-4"),
        LoginForm(error)
    )
