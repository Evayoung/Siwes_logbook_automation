"""Public landing page components - Redesigned for Anchor University SIWES."""

from fasthtml.common import *
from faststrap import Icon


def LandingPage() -> FT:
    """Modern, clean landing page for Anchor University SIWES Logbook."""
    return Html(
        Head(
            Title("SIWES Logbook | Anchor University"),
            Meta(charset="utf-8"),
            Meta(name="viewport", content="width=device-width, initial-scale=1"),
            Meta(name="description", content="Digital SIWES portal for Anchor University Computer Science students"),
            Style("""
                :root {
                    --primary: #7C3AED;
                    --primary-dark: #6D28D9;
                    --primary-light: #A78BFA;
                    --secondary: #2563EB;
                    --success: #10B981;
                    --dark: #0F172A;
                    --text-primary: #F8FAFC;
                    --text-secondary: #94A3B8;
                    --glass-bg: rgba(255, 255, 255, 0.08);
                    --glass-border: rgba(255, 255, 255, 0.15);
                    --card-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.4);
                }

                * { margin: 0; padding: 0; box-sizing: border-box; }

                body {
                    font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;
                    background: var(--dark);
                    color: var(--text-primary);
                    line-height: 1.6;
                    overflow-x: hidden;
                }

                .landing-bg {
                    position: fixed;
                    top: 0;
                    left: 0;
                    width: 100%;
                    height: 100%;
                    z-index: -1;
                    overflow: hidden;
                }

                .bg-gradient-1 {
                    position: absolute;
                    width: 800px;
                    height: 800px;
                    border-radius: 50%;
                    background: radial-gradient(circle, rgba(124, 58, 237, 0.15) 0%, transparent 70%);
                    top: -200px;
                    right: -200px;
                    animation: float 20s ease-in-out infinite;
                }

                .bg-gradient-2 {
                    position: absolute;
                    width: 600px;
                    height: 600px;
                    border-radius: 50%;
                    background: radial-gradient(circle, rgba(37, 99, 235, 0.12) 0%, transparent 70%);
                    bottom: -100px;
                    left: -100px;
                    animation: float 25s ease-in-out infinite reverse;
                }

                .bg-grid {
                    position: absolute;
                    top: 0;
                    left: 0;
                    width: 100%;
                    height: 100%;
                    background-image: 
                        linear-gradient(rgba(255, 255, 255, 0.02) 1px, transparent 1px),
                        linear-gradient(90deg, rgba(255, 255, 255, 0.02) 1px, transparent 1px);
                    background-size: 60px 60px;
                }

                @keyframes float {
                    0%, 100% { transform: translate(0, 0) rotate(0deg); }
                    50% { transform: translate(30px, 20px) rotate(5deg); }
                }

                .navbar {
                    position: sticky;
                    top: 0;
                    z-index: 1000;
                    padding: 1rem 2rem;
                    background: rgba(15, 23, 42, 0.85);
                    backdrop-filter: blur(20px);
                    -webkit-backdrop-filter: blur(20px);
                    border-bottom: 1px solid var(--glass-border);
                }

                .navbar-content {
                    max-width: 1200px;
                    margin: 0 auto;
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                }

                .nav-brand {
                    display: flex;
                    align-items: center;
                    gap: 0.75rem;
                    text-decoration: none;
                    color: var(--text-primary);
                }

                .nav-logo {
                    width: 42px;
                    height: 42px;
                    border-radius: 10px;
                    object-fit: cover;
                    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.2);
                }

                .nav-brand-text {
                    display: flex;
                    flex-direction: column;
                }

                .nav-brand-title {
                    font-size: 1.1rem;
                    font-weight: 700;
                    line-height: 1.2;
                }

                .nav-brand-subtitle {
                    font-size: 0.7rem;
                    color: var(--text-secondary);
                    letter-spacing: 0.05em;
                }

                .nav-tagline {
                    color: var(--text-secondary);
                    font-size: 0.9rem;
                }

                .hero {
                    min-height: calc(100vh - 70px);
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    padding: 4rem 2rem;
                    position: relative;
                }

                .hero-content {
                    max-width: 1200px;
                    width: 100%;
                    display: grid;
                    grid-template-columns: 1fr 1fr;
                    gap: 4rem;
                    align-items: center;
                }

                .hero-text {
                    animation: slideUp 0.8s ease-out;
                }

                @keyframes slideUp {
                    from { opacity: 0; transform: translateY(30px); }
                    to { opacity: 1; transform: translateY(0); }
                }

                .hero-badge {
                    display: inline-flex;
                    align-items: center;
                    gap: 0.5rem;
                    padding: 0.4rem 0.85rem;
                    background: rgba(124, 58, 237, 0.15);
                    border: 1px solid rgba(124, 58, 237, 0.3);
                    border-radius: 50px;
                    font-size: 0.8rem;
                    font-weight: 500;
                    color: var(--primary-light);
                    margin-bottom: 1.25rem;
                }

                .hero-title {
                    font-size: 3rem;
                    font-weight: 800;
                    line-height: 1.15;
                    margin-bottom: 1.25rem;
                }

                .hero-title-highlight {
                    background: linear-gradient(135deg, var(--primary) 0%, var(--primary-light) 50%, var(--secondary) 100%);
                    -webkit-background-clip: text;
                    -webkit-text-fill-color: transparent;
                    background-clip: text;
                }

                .hero-description {
                    font-size: 1.1rem;
                    color: var(--text-secondary);
                    margin-bottom: 2rem;
                    max-width: 500px;
                    line-height: 1.7;
                }

                .hero-cta {
                    display: flex;
                    gap: 1rem;
                    flex-wrap: wrap;
                }

                .btn-primary {
                    display: inline-flex;
                    align-items: center;
                    gap: 0.5rem;
                    padding: 0.85rem 1.75rem;
                    background: linear-gradient(135deg, var(--primary) 0%, var(--primary-dark) 100%);
                    color: white;
                    border-radius: 10px;
                    text-decoration: none;
                    font-weight: 600;
                    font-size: 1rem;
                    transition: all 0.3s ease;
                    box-shadow: 0 4px 20px rgba(124, 58, 237, 0.4);
                }

                .btn-primary:hover {
                    transform: translateY(-2px);
                    box-shadow: 0 8px 30px rgba(124, 58, 237, 0.5);
                }

                .hero-visual {
                    position: relative;
                    animation: slideUp 0.8s ease-out 0.2s both;
                }

                .hero-card {
                    background: var(--glass-bg);
                    border: 1px solid var(--glass-border);
                    border-radius: 20px;
                    padding: 1.75rem;
                    backdrop-filter: blur(20px);
                    box-shadow: var(--card-shadow);
                    position: relative;
                    overflow: hidden;
                }

                .hero-card::before {
                    content: '';
                    position: absolute;
                    top: 0;
                    left: 0;
                    right: 0;
                    height: 80px;
                    background: linear-gradient(180deg, rgba(124, 58, 237, 0.2) 0%, transparent 100%);
                }

                .hero-card-header {
                    display: flex;
                    align-items: center;
                    justify-content: space-between;
                    margin-bottom: 1.5rem;
                    position: relative;
                }

                .hero-card-title {
                    font-size: 1.1rem;
                    font-weight: 600;
                }

                .hero-stats {
                    display: grid;
                    grid-template-columns: repeat(3, 1fr);
                    gap: 0.85rem;
                    margin-bottom: 1.5rem;
                    position: relative;
                }

                .stat-item {
                    text-align: center;
                    padding: 1rem;
                    background: rgba(255, 255, 255, 0.05);
                    border-radius: 12px;
                    border: 1px solid rgba(255, 255, 255, 0.1);
                    transition: all 0.3s ease;
                }

                .stat-item:hover {
                    transform: translateY(-2px);
                    border-color: var(--primary);
                    box-shadow: 0 8px 20px rgba(124, 58, 237, 0.15);
                }

                .stat-value {
                    font-size: 1.75rem;
                    font-weight: 700;
                    color: var(--primary-light);
                    margin-bottom: 0.2rem;
                }

                .stat-label {
                    font-size: 0.8rem;
                    color: var(--text-secondary);
                }

                .hero-preview {
                    position: relative;
                    border-radius: 12px;
                    overflow: hidden;
                    border: 1px solid rgba(255, 255, 255, 0.1);
                }

                .preview-header {
                    display: flex;
                    gap: 0.5rem;
                    padding: 0.6rem 0.85rem;
                    background: rgba(0, 0, 0, 0.3);
                }

                .preview-dot {
                    width: 10px;
                    height: 10px;
                    border-radius: 50%;
                }

                .preview-dot.red { background: #EF4444; }
                .preview-dot.yellow { background: #F59E0B; }
                .preview-dot.green { background: #10B981; }

                .preview-content {
                    padding: 1.25rem;
                    background: rgba(30, 41, 59, 0.8);
                    min-height: 160px;
                }

                .preview-item {
                    display: flex;
                    align-items: center;
                    padding: 0.5rem 0;
                    border-bottom: 1px solid rgba(255, 255, 255, 0.08);
                    font-size: 0.85rem;
                    color: var(--text-secondary);
                }

                .preview-item:last-child {
                    border-bottom: none;
                }

                .preview-check {
                    color: var(--success);
                    margin-right: 0.5rem;
                    font-weight: bold;
                }

                .footer {
                    padding: 2rem;
                    border-top: 1px solid var(--glass-border);
                    background: rgba(0, 0, 0, 0.3);
                }

                .footer-content {
                    max-width: 1200px;
                    margin: 0 auto;
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                }

                .footer-brand {
                    display: flex;
                    align-items: center;
                    gap: 0.75rem;
                    text-decoration: none;
                    color: var(--text-primary);
                }

                .footer-logo {
                    width: 32px;
                    height: 32px;
                    border-radius: 8px;
                    object-fit: cover;
                }

                .footer-text {
                    color: var(--text-secondary);
                    font-size: 0.85rem;
                }

                @media (max-width: 1024px) {
                    .hero-content {
                        grid-template-columns: 1fr;
                        text-align: center;
                    }
                    .hero-description {
                        margin: 0 auto 2rem;
                    }
                    .hero-cta {
                        justify-content: center;
                    }
                }

                @media (max-width: 768px) {
                    .hero-title {
                        font-size: 2.25rem;
                    }
                    .hero-stats {
                        grid-template-columns: 1fr;
                    }
                    .hero-badge {
                        font-size: 0.75rem;
                    }
                    .hero-description {
                        font-size: 1rem;
                    }
                    .footer-content {
                        flex-direction: column;
                        gap: 1rem;
                        text-align: center;
                    }
                }
            """),
        ),
        Body(
            # Background Effects
            Div(
                Div(cls="bg-gradient-1"),
                Div(cls="bg-gradient-2"),
                Div(cls="bg-grid"),
                cls="landing-bg",
            ),

            # Navigation
            Nav(
                Div(
                    Div(
                        A(
                            Img(src="/assets/anchor-uni.jpeg", alt="AUL", cls="nav-logo"),
                            Div(
                                Span("Digital SIWES Portal", cls="nav-brand-title"),
                                Span("Anchor University", cls="nav-brand-subtitle"),
                                cls="nav-brand-text",
                            ),
                            href="/",
                            cls="nav-brand",
                        ),
                        # Span("Anchor University", cls="nav-tagline"),
                        cls="navbar-content",
                    ),
                    cls="navbar",
                ),
            ),

            # Hero Section
            Section(
                Div(
                    Div(
                        # Badge
                        Div(
                            Icon("rocket-takeoff", cls="me-1"),
                            "Final Year Project",
                            cls="hero-badge",
                        ),
                        # Title
                        H1(
                            "Streamline Your ",
                            Span("SIWES ", cls="hero-title-highlight"),
                            "Experience",
                            cls="hero-title",
                        ),
                        # Description
                        P(
                            "Digital logbook for daily activity logs, real-time supervision, and academic audit trails during your industrial training.",
                            cls="hero-description",
                        ),
                        # CTAs
                        Div(
                            A(
                                Icon("box-arrow-in-right", cls="me-1"),
                                "Sign In",
                                href="/login",
                                cls="btn-primary",
                            ),
                            cls="hero-cta",
                        ),
                        cls="hero-text",
                    ),
                    # Hero Visual
                    Div(
                        Div(
                            # Card Header
                            Div(
                                Span("Dashboard Overview", cls="hero-card-title"),
                                Span(
                                    Icon("broadcast", cls="me-1", style="color:#10B981;font-size:0.8rem;"),
                                    "Live",
                                    style="color:#10B981;font-size:0.8rem;",
                                ),
                                cls="hero-card-header",
                            ),
                            # Stats
                            Div(
                                Div(
                                    Div("156", cls="stat-value"),
                                    Div("Logs Submitted", cls="stat-label"),
                                    cls="stat-item",
                                ),
                                Div(
                                    Div("98%", cls="stat-value"),
                                    Div("Verified", cls="stat-label"),
                                    cls="stat-item",
                                ),
                                Div(
                                    Div("12", cls="stat-value"),
                                    Div("Weeks Active", cls="stat-label"),
                                    cls="stat-item",
                                ),
                                cls="hero-stats",
                            ),
                            # Preview
                            Div(
                                Div(
                                    Div(cls="preview-dot red"),
                                    Div(cls="preview-dot yellow"),
                                    Div(cls="preview-dot green"),
                                    cls="preview-header",
                                ),
                                Div(
                                    H5("Recent Entries", style="color:#F8FAFC;margin-bottom:0.75rem;font-weight:600;font-size:0.95rem;"),
                                    Div(
                                        Div(
                                            Span("✓", cls="preview-check"),
                                            "Database optimization task",
                                            cls="preview-item",
                                        ),
                                        Div(
                                            Span("✓", cls="preview-check"),
                                            "Code review session",
                                            cls="preview-item",
                                        ),
                                        Div(
                                            Span("✓", cls="preview-check"),
                                            "Fixed API endpoint bugs",
                                            cls="preview-item",
                                        ),
                                    ),
                                    cls="preview-content",
                                ),
                                cls="hero-preview",
                            ),
                            cls="hero-card",
                        ),
                        cls="hero-visual",
                    ),
                    cls="hero-content",
                ),
                cls="hero",
            ),

            # Footer
            Footer(
                Div(
                    Div(
                        A(
                            Img(src="/assets/anchor-uni.jpeg", alt="AUL", cls="footer-logo"),
                            Div(
                                Span("Digital SIWES Portal", style="font-weight:600;font-size:0.95rem;"),
                                # Span("", style="color:var(--text-secondary);font-size:0.85rem;"),
                                cls="footer-brand",
                            ),
                            href="/",
                        ),
                        cls="footer-brand",
                    ),
                    P(
                        "© 2026 Anchor University. All Rights Reserved.",
                        cls="footer-text",
                    ),
                    cls="footer-content",
                ),
                cls="footer",
            ),
        ),
    )
 