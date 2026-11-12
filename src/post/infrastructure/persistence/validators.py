from django.core.exceptions import ValidationError

ALLOWED_IMAGE_TYPES = [
    "image/jpeg",
    "image/png",
    "image/webp",
]

ALLOWED_VIDEO_TYPES = [
    "video/mp4",
    "video/webm",
]


def validate_image_mime(file):
    if file.content_type not in ALLOWED_IMAGE_TYPES:
        raise ValidationError("Only JPG, PNG and WEBP images are allowed.")


def validate_video_mime(file):
    if file.content_type not in ALLOWED_VIDEO_TYPES:
        raise ValidationError("Only MP4 and WEBM videos are allowed.")