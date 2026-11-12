from datetime import timedelta

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from core.infrastructure.persistence.models import AuditEvent


class Command(BaseCommand):
    help = "Delete audit events older than the configured retention period."

    def add_arguments(self, parser):
        parser.add_argument(
            "--days",
            type=int,
            default=90,
            help="Delete events older than this many days (default: 90).",
        )

    def handle(self, *args, **options):
        days = options["days"]
        if days < 1:
            raise CommandError("--days must be at least 1.")

        cutoff = timezone.now() - timedelta(days=days)
        deleted_count, _ = AuditEvent.objects.filter(
            created_at__lt=cutoff
        ).delete()
        self.stdout.write(
            self.style.SUCCESS(
                f"Deleted {deleted_count} old audit event(s)."
            )
        )
