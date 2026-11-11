from post.application.services import PostService
from post.infrastructure.persistence.repositories import (
    CommentRepository,
    InteractionRepository,
    PostRepository,
)
from post.infrastructure.storage import upload_validation


def get_post_service():
    return PostService(
        PostRepository(),
        CommentRepository(),
        InteractionRepository(),
        upload_validation,
    )
