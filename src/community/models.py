import uuid
from django.db import models
from common.abstracts import TimestampedModel
from users.models import User


class Community(TimestampedModel):
    name = models.CharField(max_length=100)
    description = models.TextField()
    image = models.ImageField(upload_to="community_covers/", blank=True, null=True)  # รูปปกกลุ่ม
    invite_code = models.CharField(max_length=8, unique=True, blank=True)
    is_private = models.BooleanField(default=False)

    owner = models.ForeignKey(
        User,
        on_delete=models.CASCADE
    )

    def __str__(self):
        return self.name

    # ==========================================
    # Encapsulation Methods (การซ่อน Logic ไว้ภายใน)
    # ==========================================

    def generate_invite_code(self):
        """สร้างและบันทึก Invite Code แบบสุ่ม 8 ตัวอักษร หากยังไม่มี"""
        if not self.invite_code:
            self.invite_code = str(uuid.uuid4())[:8].upper()
            self.save()
        return self.invite_code

    def is_member(self, user):
        """เช็กว่า User คนนี้เป็นสมาชิกของกลุ่มหรือยัง"""
        if not user or not user.is_authenticated:
            return False
        return CommunityMember.objects.filter(community=self, user=user).exists()

    def get_member_count(self):
        """Encapsulation: ดึงจำนวนสมาชิกทั้งหมดในกลุ่ม"""
        return CommunityMember.objects.filter(community=self).count()

    def transfer_ownership(self, new_owner):
        """Encapsulation: โอนสิทธิ์เจ้าของกลุ่มให้สมาชิกคนอื่นก่อนออก"""
        if self.is_member(new_owner):
            self.owner = new_owner
            self.save()
            return True
        return False


class CommunityMember(models.Model):
    community = models.ForeignKey(
        Community,
        on_delete=models.CASCADE
    )

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE
    )

    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("community", "user")

    def __str__(self):
        return f"{self.user.username} - {self.community.name}"