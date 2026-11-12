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


def _safe_upload_path(content_type):
    extensions = {
        "image/jpeg": "jpg",
        "image/png": "png",
        "image/webp": "webp",
        "video/mp4": "mp4",
        "video/webm": "webm",
    }

    extension = extensions.get(content_type)

    if extension is None:
        raise ValueError("??????????????????????")

    return os.path.join("posts", f"{uuid.uuid4()}.{extension}")


def upload_post_image(instance, filename):
    uploaded_file = instance.image.file
    content_type = getattr(uploaded_file, "content_type", None)

    return _safe_upload_path(content_type)


def upload_post_video(instance, filename):
    uploaded_file = instance.video.file
    content_type = getattr(uploaded_file, "content_type", None)

    return _safe_upload_path(content_type)

def upload_post_file(instance, filename):
    """?????? Migration ?????????????? upload_post_file"""
    for field_name in ("image", "video"):
        field = getattr(instance, field_name, None)
        if not field:
            continue

        try:
            uploaded_file = field.file
        except (AttributeError, ValueError):
            continue

        content_type = getattr(uploaded_file, "content_type", None)
        if content_type:
            return _safe_upload_path(content_type)

    raise ValueError("????????????????????????????????????")


class Post(TimestampedModel):
    user = models.ForeignKey(User, on_delete=models.CASCADE)

    community = models.ForeignKey(
        Community, on_delete=models.CASCADE, blank=True, null=True
    )

    content = models.TextField()

    image = models.ImageField(
        upload_to=upload_post_image,
        validators=[validate_image_mime],
        blank=True,
        null=True
    )

    video = models.FileField(
        upload_to=upload_post_video,
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