from django.db import models
import uuid
import os

from common.abstracts import TimestampedModel
from community.infrastructure.persistence.models import Community
from users.infrastructure.persistence.models import User

from .validators import (
    validate_image_mime,
    validate_video_mime,
)


def upload_post_file(instance, filename):
    ext = filename.split(".")[-1]
    return os.path.join(
        "posts",
        f"{uuid.uuid4()}.{ext}"
    )


class Post(TimestampedModel):
    user = models.ForeignKey(User, on_delete=models.CASCADE)

    community = models.ForeignKey(
        Community, on_delete=models.CASCADE, blank=True, null=True
    )

    content = models.TextField()

    image = models.ImageField(
        upload_to=upload_post_file,
        validators=[validate_image_mime],
        blank=True,
        null=True
    )

    video = models.FileField(
        upload_to=upload_post_file,
        validators=[validate_video_mime],
        blank=True,
        null=True
    )

    # 🔒 R-07: สถานะซ่อนโพสต์อัตโนมัติเมื่อโดนรายงานสแปมครบเกณฑ์
    is_hidden = models.BooleanField(default=False)

    def __str__(self):
        return self.content[:30]


class Comment(TimestampedModel):
    post = models.ForeignKey(Post, on_delete=models.CASCADE)

    user = models.ForeignKey(User, on_delete=models.CASCADE)

    content = models.TextField()


class Like(TimestampedModel):
    post = models.ForeignKey(Post, on_delete=models.CASCADE)

    user = models.ForeignKey(User, on_delete=models.CASCADE)

    class Meta:
        unique_together = ("post", "user")


class Bookmark(TimestampedModel):
    post = models.ForeignKey(
        Post,
        related_name="bookmarks",
        on_delete=models.CASCADE,
    )

    user = models.ForeignKey(
        User,
        related_name="bookmarks",
        on_delete=models.CASCADE,
    )

    class Meta:
        unique_together = ("post", "user")