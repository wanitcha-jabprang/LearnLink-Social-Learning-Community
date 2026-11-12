\
from django.core.exceptions import ValidationError


ALLOWED_IMAGE_TYPES = {
    "image/jpeg": "jpeg",
    "image/png": "png",
    "image/webp": "webp",
}

ALLOWED_VIDEO_TYPES = {
    "video/mp4": "mp4",
    "video/webm": "webm",
}


def _check_magic_bytes(file, file_type):
    file.seek(0)

    try:
        header = file.read(12)
    finally:
        file.seek(0)

    signatures = {
        "jpeg": lambda data: data.startswith(b"\xff\xd8\xff"),
        "png": lambda data: data.startswith(
            b"\x89PNG\r\n\x1a\n"
        ),
        "webp": lambda data: (
            data.startswith(b"RIFF")
            and data[8:12] == b"WEBP"
        ),
        "mp4": lambda data: (
            len(data) >= 8 and data[4:8] == b"ftyp"
        ),
        "webm": lambda data: data.startswith(
            b"\x1a\x45\xdf\xa3"
        ),
    }

    return signatures[file_type](header)


def validate_image_mime(file):
    content_type = getattr(file, "content_type", None)

    if content_type not in ALLOWED_IMAGE_TYPES:
        raise ValidationError(
            "Only JPG, PNG and WEBP images are allowed."
        )

    file_type = ALLOWED_IMAGE_TYPES[content_type]

    if not _check_magic_bytes(file, file_type):
        raise ValidationError(
            "The image file content does not match its file type."
        )


def validate_video_mime(file):
    content_type = getattr(file, "content_type", None)

    if content_type not in ALLOWED_VIDEO_TYPES:
        raise ValidationError(
            "Only MP4 and WEBM videos are allowed."
        )

    file_type = ALLOWED_VIDEO_TYPES[content_type]

    if not _check_magic_bytes(file, file_type):
        raise ValidationError(
            "The video file content does not match its file type."
        )
