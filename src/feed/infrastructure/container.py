from feed.application.services import FeedService
from feed.infrastructure.persistence.repositories import FeedRepository


def get_feed_service():
    return FeedService(FeedRepository())
