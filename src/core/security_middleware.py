from urllib.parse import urlparse

from django.conf import settings


class SecurityHeadersMiddleware:
    CONTENT_SECURITY_POLICY = (
        "default-src 'self'; "
        "base-uri 'self'; "
        "connect-src 'self'; "
        "font-src 'self' data: https://fonts.gstatic.com; "
        "form-action 'self'; "
        "frame-ancestors 'none'; "
        "img-src 'self' data: blob: https://placehold.co; "
        "media-src 'self' blob:; "
        "object-src 'none'; "
        "script-src 'self'; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com"
    )

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        response.setdefault(
            "Content-Security-Policy",
            self.CONTENT_SECURITY_POLICY,
        )
        response.setdefault(
            "Permissions-Policy",
            "camera=(), geolocation=(), microphone=()",
        )

        static_path = "/" + urlparse(settings.STATIC_URL).path.lstrip("/")
        if not static_path or not request.path.startswith(static_path):
            response["Cache-Control"] = "no-store"

        return response
