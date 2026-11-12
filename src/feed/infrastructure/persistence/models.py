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