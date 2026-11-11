from PIL import Image, UnidentifiedImageError


MAX_IMAGE_SIZE = 10 * 1024 * 1024
MAX_VIDEO_SIZE = 100 * 1024 * 1024


def validate_image(image):
    if not image:
        return None
    if image.size > MAX_IMAGE_SIZE:
        return "รูปภาพต้องมีขนาดไม่เกิน 10 MB"
    try:
        with Image.open(image) as image_file:
            image_file.verify()
    except (
        Image.DecompressionBombError,
        UnidentifiedImageError,
        OSError,
        ValueError,
    ):
        return "ไฟล์รูปภาพไม่ถูกต้อง"
    image.seek(0)
    return None


def validate_video(video):
    if not video:
        return None
    if video.size > MAX_VIDEO_SIZE:
        return "วิดีโอต้องมีขนาดไม่เกิน 100 MB"
    if not video.content_type or not video.content_type.startswith("video/"):
        return "กรุณาเลือกไฟล์วิดีโอ"
    return None
