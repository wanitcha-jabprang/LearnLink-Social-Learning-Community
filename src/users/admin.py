from django.contrib.auth.admin import UserAdmin
from django.contrib import admin

from users.infrastructure.persistence.models import Follow, User


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    fieldsets = (
        (None, {"fields": ("username", "password")}),
        ("Personal info", {"fields": ("full_name", "email")}),
        (
            "Permissions",
            {
                "fields": (
                    "is_active",
                    "is_staff",
                    "is_superuser",
                    "groups",
                    "user_permissions",
                )
            },
        ),
        ("Important dates", {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": (
                    "username",
                    "email",
                    "full_name",
                    "password1",
                    "password2",
                ),
            },
        ),
    )

    def get_readonly_fields(self, request, obj=None):
        readonly_fields = list(
            super().get_readonly_fields(request, obj)
        )

        if not request.user.is_superuser:
            readonly_fields.extend([
                "is_staff",
                "is_superuser",
            ])

        return readonly_fields

    def get_fieldsets(self, request, obj=None):
        fieldsets = super().get_fieldsets(request, obj)

        if request.user.is_superuser:
            return fieldsets

        restricted_fields = {"groups", "user_permissions"}

        return [
            (
                name,
                {
                    **options,
                    "fields": tuple(
                        field
                        for field in options.get("fields", ())
                        if field not in restricted_fields
                    ),
                },
            )
            for name, options in fieldsets
        ]


admin.site.register(Follow)
