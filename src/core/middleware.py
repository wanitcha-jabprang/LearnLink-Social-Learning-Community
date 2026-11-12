import logging

from django.db import DatabaseError

from core.infrastructure.persistence.models import AuditEvent


audit_logger = logging.getLogger("core.audit")


class AuditLogMiddleware:
    MUTATING_METHODS = {"POST", "PUT", "PATCH", "DELETE"}

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.method not in self.MUTATING_METHODS:
            return self.get_response(request)

        actor_id = self._authenticated_user_id(request)
        response = self.get_response(request)

        resolver_match = getattr(request, "resolver_match", None)
        if resolver_match is None:
            return response

        actor_id = actor_id or self._request_actor_id(request)
        target_id = next(
            (
                str(value)[:64]
                for key, value in resolver_match.kwargs.items()
                if key == "id"
                or key == "pk"
                or key.endswith("_id")
            ),
            "",
        )

        try:
            AuditEvent.objects.create(
                action=(resolver_match.view_name or "unmatched")[:128],
                actor_id=actor_id,
                method=request.method,
                target_id=target_id,
                status_code=response.status_code,
            )
        except DatabaseError as error:
            audit_logger.error(
                "Audit event was not persisted (%s)",
                type(error).__name__,
            )

        return response

    @staticmethod
    def _authenticated_user_id(request):
        user = getattr(request, "user", None)
        if user is not None and user.is_authenticated:
            return user.pk
        return None

    @classmethod
    def _request_actor_id(cls, request):
        actor_id = cls._authenticated_user_id(request)
        if actor_id is not None:
            return actor_id

        session = getattr(request, "session", None)
        if session is None:
            return None

        pending_id = session.get("mfa_pending_user_id")
        enrollment_id = session.get("mfa_enrollment_user_id")
        candidate = pending_id or enrollment_id
        try:
            return int(candidate) if candidate is not None else None
        except (TypeError, ValueError):
            return None
