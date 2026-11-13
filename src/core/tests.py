from datetime import timedelta

from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.core.management import call_command
from django.http import HttpResponse
from django.test import RequestFactory, TestCase
from django.urls import resolve, reverse
from django.utils import timezone

from core.infrastructure.persistence.models import AuditEvent
from core.middleware import AuditLogMiddleware
from core.security_middleware import SecurityHeadersMiddleware

User = get_user_model()


class AuditLogMiddlewareTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def run_middleware(self, request, *, response_status=200):
        request.resolver_match = resolve(request.path_info)
        return AuditLogMiddleware(
            lambda current_request: HttpResponse(
                status=response_status
            )
        )(request)

    def test_records_mutations_without_request_body_or_headers(self):
        request = self.factory.post(
            reverse("register"),
            {
                "password": "must-not-be-recorded",
                "otp": "123456",
            },
        )
        request.user = AnonymousUser()
        request.session = {}

        self.run_middleware(request, response_status=302)

        event = AuditEvent.objects.get()
        self.assertEqual(event.action, "register")
        self.assertEqual(event.method, "POST")
        self.assertEqual(event.status_code, 302)
        self.assertIsNone(event.actor_id)
        self.assertEqual(event.target_id, "")

    def test_keeps_actor_id_when_logout_clears_the_request_user(self):
        user = User.objects.create_user(
            username="audit_user",
            email="audit@example.com",
            password="StrongPass123!",
            full_name="Audit User",
        )
        request = self.factory.post(reverse("logout"))
        request.user = user
        request.session = {}

        def logout_response(current_request):
            current_request.user = AnonymousUser()
            return HttpResponse(status=302)

        request.resolver_match = resolve(request.path_info)
        AuditLogMiddleware(logout_response)(request)

        event = AuditEvent.objects.get()
        self.assertEqual(event.action, "logout")
        self.assertEqual(event.actor_id, user.pk)

    def test_does_not_record_read_only_requests(self):
        request = self.factory.get("/")
        request.user = AnonymousUser()
        request.session = {}

        self.run_middleware(request)

        self.assertFalse(AuditEvent.objects.exists())

    def test_retention_command_deletes_events_older_than_ninety_days(self):
        old_event = AuditEvent.objects.create(
            action="delete_post",
            method="POST",
            status_code=200,
        )
        AuditEvent.objects.filter(pk=old_event.pk).update(
            created_at=timezone.now() - timedelta(days=91)
        )
        recent_event = AuditEvent.objects.create(
            action="create_post",
            method="POST",
            status_code=201,
        )

        call_command("cleanup_audit_events")

        self.assertFalse(AuditEvent.objects.filter(pk=old_event.pk).exists())
        self.assertTrue(AuditEvent.objects.filter(pk=recent_event.pk).exists())


class SecurityHeadersMiddlewareTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def test_sets_security_headers_and_prevents_html_caching(self):
        middleware = SecurityHeadersMiddleware(
            lambda request: HttpResponse("<html></html>")
        )

        response = middleware(self.factory.get("/"))

        self.assertIn("base-uri 'self'", response["Content-Security-Policy"])
        self.assertIn(
            "frame-ancestors 'none'",
            response["Content-Security-Policy"],
        )
        self.assertEqual(
            response["Permissions-Policy"],
            "camera=(), geolocation=(), microphone=()",
        )
        self.assertEqual(response["Cache-Control"], "no-store")

    def test_preserves_static_asset_cache_policy(self):
        def serve_static(request):
            response = HttpResponse("body")
            response["Cache-Control"] = "public, max-age=3600"
            return response

        middleware = SecurityHeadersMiddleware(serve_static)
        response = middleware(self.factory.get("/static/app.css"))

        self.assertEqual(
            response["Cache-Control"],
            "public, max-age=3600",
        )
