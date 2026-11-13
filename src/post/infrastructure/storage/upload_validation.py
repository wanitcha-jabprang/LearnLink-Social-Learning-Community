
import warnings
from io import BytesIO

from django.core.files.base import ContentFile
from PIL import (
    Image,
    ImageOps,
    UnidentifiedImageError,
)

MAX_IMAGE_SIZE = 10 * 1024 * 1024
MAX_VIDEO_SIZE = 100 * 1024 * 1024

ALLOWED_IMAGE_FORMATS = {
    "JPEG": "image/jpeg",
    "PNG": "image/png",
    "WEBP": "image/webp",
}

ALLOWED_VIDEO_TYPES = {
    "video/mp4",
    "video/webm",
}


def validate_image(image):
    if not image:
        return None

    if image.size > MAX_IMAGE_SIZE:
        return "รูปภาพต้องมีขนาดไม่เกิน 10 MB"

    try:
        image.seek(0)

        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)

            with Image.open(image) as img:
                detected_format = img.format

                if detected_format not in ALLOWED_IMAGE_FORMATS:
                    return "รองรับเฉพาะไฟล์รูปภาพ JPEG, PNG และ WEBP"

                expected_mime = ALLOWED_IMAGE_FORMATS[detected_format]

                if image.content_type != expected_mime:
                    return "ประเภทไฟล์รูปภาพไม่ถูกต้อง"

                img.verify()

        image.seek(0)

        with Image.open(image) as img:
            img.load()

        image.seek(0)
        return None

    except (
        UnidentifiedImageError,
        OSError,
        ValueError,
        Image.DecompressionBombError,
        Image.DecompressionBombWarning,
    ):
        return "ไฟล์รูปภาพไม่ถูกต้อง"

    except Exception:
        return "ไม่สามารถตรวจสอบไฟล์รูปภาพได้"

    finally:
        image.seek(0)


def reencode_image(image):
    if not image:
        return None

    image.seek(0)

    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)

            with Image.open(image) as source:
                if source.format not in ALLOWED_IMAGE_FORMATS:
                    raise ValueError(
                        "รองรับเฉพาะไฟล์รูปภาพ JPEG, PNG และ WEBP"
                    )

                if getattr(source, "is_animated", False):
                    raise ValueError("ไม่รองรับรูปภาพเคลื่อนไหว")

                source.load()
                output_format = source.format

                cleaned = ImageOps.exif_transpose(source)

                if output_format == "JPEG":
                    if cleaned.mode not in ("RGB", "L"):
                        if "A" in cleaned.getbands():
                            background = Image.new(
                                "RGB",
                                cleaned.size,
                                (255, 255, 255),
                            )
                            background.paste(
                                cleaned,
                                mask=cleaned.getchannel("A"),
                            )
                            cleaned = background
                        else:
                            cleaned = cleaned.convert("RGB")

                elif output_format == "PNG":
                    if cleaned.mode not in ("RGB", "RGBA", "L", "LA"):
                        cleaned = cleaned.convert("RGBA")

                elif output_format == "WEBP":
                    if cleaned.mode not in ("RGB", "RGBA"):
                        cleaned = cleaned.convert("RGBA")

                output = BytesIO()

                save_options = {"format": output_format}

                if output_format == "JPEG":
                    save_options.update({
                        "quality": 90,
                        "optimize": True,
                    })
                elif output_format == "PNG":
                    save_options.update({"optimize": True})
                elif output_format == "WEBP":
                    save_options.update({
                        "quality": 90,
                        "method": 6,
                    })

                cleaned.save(output, **save_options)

                if cleaned is not source:
                    cleaned.close()

        extension = {
            "JPEG": "jpg",
            "PNG": "png",
            "WEBP": "webp",
        }[output_format]

        sanitized = ContentFile(
            output.getvalue(),
            name=f"sanitized.{extension}",
        )

        if sanitized.size > MAX_IMAGE_SIZE:
            raise ValueError(
                "รูปภาพหลังประมวลผลมีขนาดเกิน 10 MB"
            )

        sanitized.content_type = ALLOWED_IMAGE_FORMATS[output_format]

        return sanitized

    except ValueError:
        raise

    except Exception as exc:
        raise ValueError(
            "ไม่สามารถประมวลผลรูปภาพได้"
        ) from exc

    finally:
        image.seek(0)


def validate_video(video):
    if not video:
        return None

    if video.size > MAX_VIDEO_SIZE:
        return "วิดีโอต้องมีขนาดไม่เกิน 100 MB"

    if video.size == 0:
        return "ไฟล์วิดีโอว่างเปล่า"

    if not video.content_type.startswith("video/"):
        return "กรุณาเลือกไฟล์วิดีโอ"

    if video.content_type not in ALLOWED_VIDEO_TYPES:
        return "รองรับเฉพาะไฟล์ MP4 และ WEBM"

    try:
        video.seek(0)
        header = video.read(16)
        video.seek(0)

        if video.content_type == "video/mp4":
            if len(header) < 12 or header[4:8] != b"ftyp":
                return "ไฟล์ MP4 ไม่ถูกต้อง"

        elif video.content_type == "video/webm":
            if not header.startswith(b"\x1A\x45\xDF\xA3"):
                return "ไฟล์ WEBM ไม่ถูกต้อง"

        return None

    except (OSError, ValueError):
        return "ไม่สามารถตรวจสอบไฟล์วิดีโอได้"

    finally:
        video.seek(0)


__all__ = [
    "MAX_IMAGE_SIZE",
    "MAX_VIDEO_SIZE",
    "validate_image",
    "validate_video",
    "reencode_image",
]
