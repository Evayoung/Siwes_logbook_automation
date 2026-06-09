"""HTTP cache-control middleware for protected app pages."""

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request


class NoStoreMiddleware(BaseHTTPMiddleware):
    """Prevent stale protected screens from showing after logout/back."""

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        path = request.url.path

        static_prefixes = ("/static/", "/assets/")
        static_exact = {"/manifest.json", "/sw.js", "/favicon.ico", "/health"}
        if path.startswith(static_prefixes) or path in static_exact:
            return response

        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
        return response
