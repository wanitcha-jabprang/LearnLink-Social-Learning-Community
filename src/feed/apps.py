from common.apps import LayeredFeatureConfig


class FeedConfig(LayeredFeatureConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'feed'
