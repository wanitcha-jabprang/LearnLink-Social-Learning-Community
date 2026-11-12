from django.contrib import admin

from core.infrastructure.persistence.models import AuditEvent


@admin.register(AuditEvent)
class AuditEventAdmin(admin.ModelAdmin):
    list_display = (
        "created_at",
        "actor_id",
        "action",
        "method",
        "target_id",
        "status_code",
    )
    list_filter = ("method", "status_code")
    search_fields = ("action", "target_id")
    readonly_fields = (
        "action",
        "actor_id",
        "method",
        "target_id",
        "status_code",
        "created_at",
    )
    ordering = ("-created_at",)

    def has_module_permission(self, request):
        return request.user.is_superuser

    def has_view_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
