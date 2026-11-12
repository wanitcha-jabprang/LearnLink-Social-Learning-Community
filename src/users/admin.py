
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import User, Follow


@admin.register(User)
class CustomUserAdmin(UserAdmin):
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


admin.site.register(Follow)
