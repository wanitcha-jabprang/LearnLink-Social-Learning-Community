
import os
import uuid

from PIL import Image, UnidentifiedImageError
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.files.storage import FileSystemStorage
from django.db import models
from django.utils.deconstruct import deconstructible

from common.abstracts import TimestampedModel
from common.infrastructure.storage.upload_validation import scan_uploaded_file
from users.infrastructure.persistence.models import User


# =========================================================
# Upload Validation & Random Filename
# =========================================================

def get_detected_image_extension(image):
    try:
        image.seek(0)

        with Image.open(image) as img:
            detected_format = img.format

    except (UnidentifiedImageError, OSError, ValueError):
        raise ValidationError("ไฟล์รูปภาพไม่ถูกต้อง")

    finally:
        image.seek(0)

    extensions = {
        "JPEG": ".jpg",
        "PNG": ".png",
        "WEBP": ".webp",
    }

    extension = extensions.get(detected_format)

    if not extension:
        raise ValidationError("ไม่รองรับรูปแบบภาพนี้")

    return extension


def upload_community_image(instance, filename):
    image = instance.image.file
    extension = get_detected_image_extension(image)

    return os.path.join(
        "communities",
        "images",
        f"{uuid.uuid4().hex}{extension}",
    )


def upload_community_document(instance, filename):
    uploaded_file = instance.file.file

    # จำกัดขนาดเอกสารไม่เกิน 20 MB
    max_document_size = 20 * 1024 * 1024

    if uploaded_file.size == 0:
        raise ValidationError("ไฟล์เอกสารว่างเปล่า")

    if uploaded_file.size > max_document_size:
        raise ValidationError("ไฟล์เอกสารต้องมีขนาดไม่เกิน 20 MB")

    # ตรวจสอบ PDF จากเนื้อหาไฟล์จริง
    try:
        uploaded_file.seek(0)
        header = uploaded_file.read(8)
        uploaded_file.seek(0)

    except (OSError, ValueError):
        raise ValidationError("ไม่สามารถอ่านไฟล์เอกสารได้")

    if not header.startswith(b"%PDF-"):
        raise ValidationError("รองรับเฉพาะเอกสาร PDF")

    # สแกนไวรัสด้วย ClamAV ก่อนบันทึก
    scan_error = scan_uploaded_file(uploaded_file)

    if scan_error:
        raise ValidationError(scan_error)

    # สุ่มชื่อไฟล์และกำหนดนามสกุล PDF เอง
    return os.path.join(
        "protected_community_docs",
        f"{uuid.uuid4().hex}.pdf",
    )


# =========================================================
# Private Storage
# =========================================================

@deconstructible
class PrivateMediaStorage(FileSystemStorage):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault(
            "location",
            os.path.join(settings.BASE_DIR, "private_media"),
        )
        kwargs.setdefault("base_url", "")
        super().__init__(*args, **kwargs)

    def url(self, name):
        raise ValueError(
            "This file is not accessible via a public URL."
        )


private_storage = PrivateMediaStorage()


# =========================================================
# Community
# =========================================================

class Community(TimestampedModel):
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    name = models.CharField(max_length=100)
    description = models.TextField()

    image = models.ImageField(
        upload_to=upload_community_image,
        blank=True,
        null=True,
    )

    invite_code = models.CharField(
        max_length=8,
        unique=True,
        blank=True,
    )

    is_private = models.BooleanField(default=False)

    owner = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
    )

    def __str__(self):
        return self.name

    def is_member(self, user):
        if not user or not user.is_authenticated:
            return False

        if self.owner == user:
            return True

        return CommunityMember.objects.filter(
            community=self,
            user=user,
        ).exists()

    def is_owner(self, user):
        if not user or not user.is_authenticated:
            return False

        return self.owner == user

    def get_member_count(self):
        return CommunityMember.objects.filter(
            community=self,
        ).count()


# =========================================================
# Community Member
# =========================================================

class CommunityMember(models.Model):
    community = models.ForeignKey(
        Community,
        on_delete=models.CASCADE,
    )

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
    )

    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("community", "user")

    def __str__(self):
        return f"{self.user.username} in {self.community.name}"


# =========================================================
# Private Community Documents
# =========================================================

class CommunityDocument(TimestampedModel):
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    community = models.ForeignKey(
        Community,
        on_delete=models.CASCADE,
        related_name="documents",
    )

    uploaded_by = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
    )

    title = models.CharField(max_length=255)

    file = models.FileField(
        upload_to=upload_community_document,
        storage=private_storage,
    )

    is_private = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.title} - {self.community.name}"


# =========================================================
# Community Reports & Moderation
# =========================================================

class CommunityReport(TimestampedModel):
    REPORT_TYPES = (
        ("POST", "Report Post"),
        ("USER", "Report User"),
    )

    STATUS_CHOICES = (
        ("PENDING", "Pending Review"),
        ("RESOLVED", "Resolved / Hidden"),
        ("DISMISSED", "Dismissed"),
    )

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    community = models.ForeignKey(
        Community,
        on_delete=models.CASCADE,
        related_name="reports",
    )

    reporter = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="submitted_reports",
    )

    reported_user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="reports_against",
    )

    report_type = models.CharField(
        max_length=10,
        choices=REPORT_TYPES,
        default="POST",
    )

    target_id = models.CharField(
        max_length=255,
        help_text="ID ของโพสต์หรือไอเท็มที่โดนรายงาน",
    )

    reason = models.TextField()

    status = models.CharField(
        max_length=15,
        choices=STATUS_CHOICES,
        default="PENDING",
    )

    def __str__(self):
        return (
            f"[{self.report_type}] Report in "
            f"{self.community.name} by {self.reporter.username}"
        )
