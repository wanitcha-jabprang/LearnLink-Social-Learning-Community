from common.infrastructure.storage.upload_validation import (
    MAX_IMAGE_SIZE,
    validate_image,
)


MAX_VIDEO_SIZE = 100 * 1024 * 1024


def validate_video(video):
    if not video:
        return None
    if video.size > MAX_VIDEO_SIZE:
        return "วิดีโอต้องมีขนาดไม่เกิน 100 MB"
    if not video.content_type or not video.content_type.startswith("video/"):
        return "กรุณาเลือกไฟล์วิดีโอ"
    return None
