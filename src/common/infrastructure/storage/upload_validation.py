
import logging
import os
import socket
import struct
import warnings
from io import BytesIO

from django.core.files.base import ContentFile
from PIL import Image, ImageOps, UnidentifiedImageError


MAX_IMAGE_SIZE = 10 * 1024 * 1024
MAX_VIDEO_SIZE = 100 * 1024 * 1024

CLAMAV_HOST = os.getenv("CLAMAV_HOST", "clamav").strip() or "clamav"
if (
    os.getenv("RAILWAY_ENVIRONMENT_ID")
    or os.getenv("RAILWAY_ENVIRONMENT_NAME")
) and "." not in CLAMAV_HOST:
    CLAMAV_HOST = f"{CLAMAV_HOST}.railway.internal"
CLAMAV_PORT = int(os.getenv("CLAMAV_PORT", "3310"))
CLAMAV_TIMEOUT = 120
CLAMAV_CHUNK_SIZE = 64 * 1024
logger = logging.getLogger(__name__)

ALLOWED_IMAGE_FORMATS = {
    "JPEG": "image/jpeg",
    "PNG": "image/png",
    "WEBP": "image/webp",
}

ALLOWED_VIDEO_TYPES = {
    "video/mp4",
    "video/webm",
}


def scan_uploaded_file(uploaded_file):
    """
    Scan an uploaded file using ClamAV INSTREAM protocol.
    Fail closed when ClamAV is unavailable or returns an error.
    """

    if not uploaded_file:
        return None

    try:
        uploaded_file.seek(0)

        with socket.create_connection(
            (CLAMAV_HOST, CLAMAV_PORT),
            timeout=CLAMAV_TIMEOUT,
        ) as connection:

            connection.settimeout(CLAMAV_TIMEOUT)
            connection.sendall(b"zINSTREAM\x00")

            while True:
                chunk = uploaded_file.read(CLAMAV_CHUNK_SIZE)

                if not chunk:
                    break

                connection.sendall(struct.pack("!I", len(chunk)))
                connection.sendall(chunk)

            # End of stream
            connection.sendall(struct.pack("!I", 0))

            response = bytearray()

            while len(response) < 4096:
                data = connection.recv(4096 - len(response))

                if not data:
                    break

                response.extend(data)

                if b"\x00" in response:
                    break

        result = bytes(response).decode(
            "utf-8",
            errors="replace",
        ).strip("\x00\r\n ")

        if result.endswith("OK"):
            return None

        if "FOUND" in result:
            return "ตรวจพบไฟล์ที่อาจเป็นอันตราย ไม่อนุญาตให้อัปโหลด"

        return "ระบบสแกนไวรัสไม่สามารถตรวจสอบไฟล์ได้"

    except (OSError, socket.timeout, ValueError) as error:
        logger.warning(
            "ClamAV scan unavailable (%s)",
            type(error).__name__,
        )
        return "ระบบสแกนไวรัสไม่พร้อมใช้งาน กรุณาลองใหม่ภายหลัง"

    except Exception as error:
        logger.error(
            "ClamAV scan failed (%s)",
            type(error).__name__,
        )
        return "เกิดข้อผิดพลาดระหว่างตรวจสอบไวรัส"

    finally:
        try:
            uploaded_file.seek(0)
        except (OSError, ValueError):
            pass


def validate_image(image):
    if not image:
        return None

    if image.size > MAX_IMAGE_SIZE:
        return "รูปภาพต้องมีขนาดไม่เกิน 10 MB"

    # Scan before Pillow processes the image
    scan_error = scan_uploaded_file(image)

    if scan_error:
        return scan_error

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

        return None

    except (Image.DecompressionBombError, Image.DecompressionBombWarning):
        return "รูปภาพมีขนาดพิกเซลเกินกำหนด"

    except (
        UnidentifiedImageError,
        OSError,
        ValueError,
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
                                "RGB", cleaned.size, (255, 255, 255)
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
                    save_options.update(quality=90, optimize=True)
                elif output_format == "PNG":
                    save_options.update(optimize=True)
                elif output_format == "WEBP":
                    save_options.update(quality=90, method=6)

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
            raise ValueError("รูปภาพหลังประมวลผลมีขนาดเกิน 10 MB")

        sanitized.content_type = ALLOWED_IMAGE_FORMATS[output_format]
        return sanitized

    except ValueError:
        raise

    except Exception as exc:
        raise ValueError("ไม่สามารถประมวลผลรูปภาพได้") from exc

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

    # Scan before saving the video
    scan_error = scan_uploaded_file(video)

    if scan_error:
        return scan_error

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
    "scan_uploaded_file",
]
