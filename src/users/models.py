from django.contrib.auth.models import AbstractUser
from django.db import models
from common.abstracts import TimestampedModel


class User(AbstractUser, TimestampedModel):
    full_name = models.CharField(max_length=100)
    bio = models.TextField(blank=True)
    profile_image = models.ImageField(
        upload_to="profiles/",
        blank=True,
        null=True
    )
    profile_cover = models.ImageField(
        upload_to="profile_covers/",
        blank=True,
        null=True,
    )

    def __str__(self):
        return self.username


class Follow(TimestampedModel):
    follower = models.ForeignKey(
        User,
        related_name="following",
        on_delete=models.CASCADE
    )

    following = models.ForeignKey(
        User,
        related_name="followers",
        on_delete=models.CASCADE
    )

    class Meta:
        unique_together = ("follower", "following")