from common.apps import LayeredFeatureConfig


class CoreConfig(LayeredFeatureConfig):
    name = "core"
    default_auto_field = "django.db.models.BigAutoField"
