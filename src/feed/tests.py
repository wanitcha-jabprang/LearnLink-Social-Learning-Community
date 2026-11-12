from datetime import datetime, timedelta, timezone as dt_timezone
from unittest.mock import patch

from django.test import TestCase

from feed.infrastructure.persistence.models import RateLimitBucket
from feed.presentation.views import (
    _increment_rate_limit,
    cleanup_expired_rate_limit_buckets,
)


class RateLimitBucketTests(TestCase):
    def test_counter_resets_when_time_window_changes(self):
        key = "rl_feed_view_ip_127.0.0.1"
        t1 = datetime(2026, 11, 12, 10, 0, 10, tzinfo=dt_timezone.utc)
        t2 = datetime(2026, 11, 12, 10, 1, 5, tzinfo=dt_timezone.utc)

        with patch("feed.presentation.views.timezone.now", return_value=t1):
            self.assertEqual(_increment_rate_limit(key, 60), 1)
            self.assertEqual(_increment_rate_limit(key, 60), 2)

        with patch("feed.presentation.views.timezone.now", return_value=t2):
            self.assertEqual(_increment_rate_limit(key, 60), 1)
            bucket = RateLimitBucket.objects.get(key=key)
            self.assertEqual(bucket.count, 1)

    def test_cleanup_expired_rate_limit_buckets_removes_old_records(self):
        now = datetime(2026, 11, 12, 12, 0, 0, tzinfo=dt_timezone.utc)
        RateLimitBucket.objects.create(
            key="old_ip",
            count=5,
            window_start=now - timedelta(hours=2),
        )
        RateLimitBucket.objects.create(
            key="active_ip",
            count=2,
            window_start=now - timedelta(minutes=5),
        )

        with patch("feed.presentation.views.timezone.now", return_value=now):
            deleted = cleanup_expired_rate_limit_buckets(retention_seconds=3600)

        self.assertEqual(deleted, 1)
        self.assertFalse(RateLimitBucket.objects.filter(key="old_ip").exists())
        self.assertTrue(RateLimitBucket.objects.filter(key="active_ip").exists())