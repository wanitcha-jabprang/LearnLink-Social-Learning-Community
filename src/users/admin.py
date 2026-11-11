from django.contrib import admin
from users.infrastructure.persistence.models import Follow, User

admin.site.register(User)
admin.site.register(Follow)