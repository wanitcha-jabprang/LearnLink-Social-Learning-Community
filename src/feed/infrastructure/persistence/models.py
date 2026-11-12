from django.db import models

from common.abstracts.models import TimestampedModel
from post.infrastructure.persistence.models import Post
from users.infrastructure.persistence.models import User


class SpamReport(TimestampedModel):
    post = models.ForeignKey(
        Post,
        on_delete=models.CASCADE,
        related_name="spam_reports",
    )
    reporter = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="submitted_spam_reports",
    )
    reason = models.CharField(max_length=255, default="Spam")

    class Meta:
        unique_together = ("post", "reporter")

    def __str__(self):
        return f"Report on Post {self.post_id} by {self.reporter}"


class RateLimitBucket(models.Model):
    key = models.CharField(max_length=120, unique=True)
    count = models.PositiveIntegerField(default=0)
    window_start = models.DateTimeField()

    class Meta:
        db_table = "feed_rate_limit_bucket"