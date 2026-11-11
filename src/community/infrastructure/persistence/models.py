import uuid
from django.db import models

from common.abstracts import TimestampedModel
from users.infrastructure.persistence.models import User


class Community(TimestampedModel):
    # 🔒 R-03: ใช้ UUID Primary Key ป้องกัน IDOR / Predictable Sequential IDs
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100)
    description = models.TextField()
    image = models.ImageField(
        upload_to="community_covers/", blank=True, null=True
    )
    invite_code = models.CharField(max_length=8, unique=True, blank=True)
    is_private = models.BooleanField(default=False)
    owner = models.ForeignKey(User, on_delete=models.CASCADE)

    def __str__(self):
        return self.name

    # 🔒 R-03 Authorization Helper Methods
    def is_member(self, user):
        if not user or not user.is_authenticated:
            return False
        if self.owner == user:
            return True
        return CommunityMember.objects.filter(community=self, user=user).exists()

    def is_owner(self, user):
        if not user or not user.is_authenticated:
            return False
        return self.owner == user

    def get_member_count(self):
        return CommunityMember.objects.filter(community=self).count()


class CommunityMember(models.Model):
    community = models.ForeignKey(Community, on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("community", "user")

    def __str__(self):
        return f"{self.user.username} in {self.community.name}"


# 🔒 R-04: Model สำหรับจัดเก็บไฟล์เอกสารประจำชุมชนอย่างปลอดภัย (Private Files)
class CommunityDocument(TimestampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    community = models.ForeignKey(Community, on_delete=models.CASCADE, related_name="documents")
    uploaded_by = models.ForeignKey(User, on_delete=models.CASCADE)
    title = models.CharField(max_length=255)
    file = models.FileField(upload_to="protected_community_docs/")
    is_private = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.title} - {self.community.name}"


# 🔒 R-07: Model สำหรับระบบรายงานสแปม / เนื้อหาไม่เหมาะสม (Spam & Moderation)
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

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    community = models.ForeignKey(Community, on_delete=models.CASCADE, related_name="reports")
    reporter = models.ForeignKey(User, on_delete=models.CASCADE, related_name="submitted_reports")
    reported_user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True, related_name="reports_against")
    report_type = models.CharField(max_length=10, choices=REPORT_TYPES, default="POST")
    target_id = models.CharField(max_length=255, help_text="ID ของโพสต์หรือไอเท็มที่โดนรายงาน")
    reason = models.TextField()
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default="PENDING")

    def __str__(self):
        return f"[{self.report_type}] Report in {self.community.name} by {self.reporter.username}"