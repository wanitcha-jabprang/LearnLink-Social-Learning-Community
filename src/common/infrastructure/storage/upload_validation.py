import warnings

from PIL import Image, UnidentifiedImageError

MAX_IMAGE_SIZE = 10 * 1024 * 1024
ALLOWED_IMAGE_FORMATS = frozenset({"JPEG", "PNG", "WEBP"})


def validate_image(image):
    if not image:
        return None
    if image.size > MAX_IMAGE_SIZE:
        return "รูปภาพต้องมีขนาดไม่เกิน 10 MB"
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(image) as image_file:
                if image_file.format not in ALLOWED_IMAGE_FORMATS:
                    return "รองรับเฉพาะไฟล์รูปภาพ JPEG, PNG และ WEBP"
                image_file.verify()
    except (Image.DecompressionBombError, Image.DecompressionBombWarning):
        return "รูปภาพมีขนาดพิกเซลเกินกำหนด"
    except (
        UnidentifiedImageError,
        OSError,
        ValueError,
    ):
        return "ไฟล์รูปภาพไม่ถูกต้อง"
    image.seek(0)
    return None
