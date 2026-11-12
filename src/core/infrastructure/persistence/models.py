from django.db import models


class AuditEvent(models.Model):
    action = models.CharField(max_length=128)
    actor_id = models.PositiveBigIntegerField(
        null=True,
        blank=True,
        db_index=True,
    )
    method = models.CharField(max_length=8)
    target_id = models.CharField(max_length=64, blank=True)
    status_code = models.PositiveSmallIntegerField()
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ("-created_at",)
        indexes = [
            models.Index(fields=["action", "created_at"]),
        ]

    def __str__(self):
        return f"{self.action} ({self.status_code})"
