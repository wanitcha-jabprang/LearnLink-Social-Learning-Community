from dataclasses import dataclass

from post.application.services import (
    CommentService,
    PostAccessService,
    PostInteractionService,
    PostService,
)
from post.infrastructure.persistence.repositories import (
    CommentRepository,
    InteractionRepository,
    PostRepository,
)
from post.infrastructure.storage import upload_validation


@dataclass(frozen=True)
class PostServices:
    posts: PostService
    comments: CommentService
    interactions: PostInteractionService


def get_post_services():
    posts = PostRepository()
    comments = CommentRepository()
    access = PostAccessService(posts)
    return PostServices(
        posts=PostService(posts, upload_validation, access),
        comments=CommentService(comments, access),
        interactions=PostInteractionService(InteractionRepository(), access),
    )
