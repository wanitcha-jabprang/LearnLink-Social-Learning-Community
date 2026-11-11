from common.apps import LayeredFeatureConfig


class PostConfig(LayeredFeatureConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "post"
