from django.contrib import admin

from community.infrastructure.persistence.models import (
    Community,
    CommunityMember,
)

admin.site.register(Community)
admin.site.register(CommunityMember)
