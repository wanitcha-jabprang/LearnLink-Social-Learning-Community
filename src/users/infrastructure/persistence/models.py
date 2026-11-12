from django.contrib.auth.models import AbstractUser
from django.db import models

from common.abstracts.models import TimestampedModel


class User(AbstractUser, TimestampedModel):
    first_name = None
    last_name = None
    full_name = models.CharField(max_length=100)
    bio = models.TextField(blank=True)
    profile_image = models.ImageField(
        upload_to="profiles/", blank=True, null=True
    )
    profile_cover = models.ImageField(
        upload_to="profile_covers/",
        blank=True,
        null=True,
    )
    # Multi-Factor Authentication
    mfa_enabled = models.BooleanField(default=False)
    mfa_secret_encrypted = models.TextField(blank=True, default="")
    mfa_last_used_step = models.BigIntegerField(
        null=True,
        blank=True,
        default=None,
    )

    def __str__(self):
        return self.username


class Follow(TimestampedModel):
    follower = models.ForeignKey(
        User, related_name="following", on_delete=models.CASCADE
    )

    following = models.ForeignKey(
        User, related_name="followers", on_delete=models.CASCADE
    )

    class Meta:
        unique_together = ("follower", "following")

class LoginAttempt(models.Model):
    key = models.CharField(max_length=64, unique=True)
    attempts = models.PositiveSmallIntegerField(default=0)
    window_started_at = models.DateTimeField()

    def __str__(self):
        return f"{self.key}: {self.attempts}"
