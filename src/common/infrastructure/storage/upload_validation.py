
import warnings

from PIL import Image, UnidentifiedImageError

MAX_IMAGE_SIZE = 10 * 1024 * 1024

ALLOWED_IMAGE_TYPES = {
    "image/jpeg": "JPEG",
    "image/png": "PNG",
    "image/webp": "WEBP",
}


def validate_image(image):
    if not image:
        return None

    if image.size > MAX_IMAGE_SIZE:
        return "รูปภาพต้องมีขนาดไม่เกิน 10 MB"

    content_type = getattr(image, "content_type", None)

    if content_type not in ALLOWED_IMAGE_TYPES:
        return "รองรับเฉพาะไฟล์รูปภาพ JPEG, PNG และ WEBP"

    try:
        with warnings.catch_warnings():
            warnings.simplefilter(
                "error",
                Image.DecompressionBombWarning
            )

            with Image.open(image) as image_file:
                if image_file.format != ALLOWED_IMAGE_TYPES[content_type]:
                    return "ชนิด MIME ไม่ตรงกับเนื้อหาไฟล์"

                image_file.verify()

    except (
        Image.DecompressionBombError,
        Image.DecompressionBombWarning
    ):
        return "รูปภาพมีขนาดพิกเซลเกินกำหนด"

    except (
        UnidentifiedImageError,
        OSError,
        ValueError
    ):
        return "ไฟล์รูปภาพไม่ถูกต้อง"

    finally:
        image.seek(0)

    return None
