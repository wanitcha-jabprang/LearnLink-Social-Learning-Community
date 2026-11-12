
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from users.models import LoginAttempt


class Command(BaseCommand):
    help = "Delete old login attempt records."

    def add_arguments(self, parser):
        parser.add_argument(
            "--days",
            type=int,
            default=30,
            help="Delete records older than this many days (default: 30).",
        )

    def handle(self, *args, **options):
        days = options["days"]

        if days < 1:
            self.stderr.write(
                self.style.ERROR("--days must be at least 1.")
            )
            return

        cutoff = timezone.now() - timedelta(days=days)

        deleted_count, _ = LoginAttempt.objects.filter(
            window_started_at__lt=cutoff
        ).delete()

        self.stdout.write(
            self.style.SUCCESS(
                f"Deleted {deleted_count} old login attempt record(s)."
            )
        )
