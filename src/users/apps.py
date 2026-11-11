from common.apps import LayeredFeatureConfig


class UsersConfig(LayeredFeatureConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "users"