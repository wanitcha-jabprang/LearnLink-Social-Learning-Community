
from django.core.exceptions import ValidationError

from common.infrastructure.storage.upload_validation import (
    MAX_IMAGE_SIZE,
    validate_image as validate_image_content,
)

from post.infrastructure.persistence.validators import (
    validate_image_mime,
    validate_video_mime,
)


def validate_image(image):
    if not image:
        return None

    error = validate_image_content(image)
    if error:
        return error

    try:
        validate_image_mime(image)
    except ValidationError as error:
        return error.messages[0]

    return None


MAX_VIDEO_SIZE = 100 * 1024 * 1024


def validate_video(video):
    if not video:
        return None

    if video.size > MAX_VIDEO_SIZE:
        return "วิดีโอต้องมีขนาดไม่เกิน 100 MB"

    try:
        validate_video_mime(video)
    except ValidationError as error:
        return "กรุณาเลือกไฟล์วิดีโอ" if (
            getattr(video, "content_type", None)
            not in {"video/mp4", "video/webm"}
        ) else "ชนิด MIME ไม่ตรงกับเนื้อหาวิดีโอ"

    except (OSError, ValueError, AttributeError):
        return "ไม่สามารถอ่านไฟล์วิดีโอได้"

    return None


__all__ = [
    "MAX_IMAGE_SIZE",
    "MAX_VIDEO_SIZE",
    "validate_image",
    "validate_video",
]
