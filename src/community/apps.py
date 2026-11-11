from common.apps import LayeredFeatureConfig


class CommunityConfig(LayeredFeatureConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'community'
