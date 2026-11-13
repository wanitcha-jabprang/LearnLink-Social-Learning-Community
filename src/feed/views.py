from functools import wraps

from django.contrib.auth.decorators import login_required
from django.db import IntegrityError, transaction
from django.db.models import F, Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from feed.infrastructure.container import get_feed_service
from feed.infrastructure.persistence.models import RateLimitBucket, SpamReport
from post.infrastructure.persistence.models import Post


def _increment_rate_limit(key: str, window_seconds: int) -> int:
    """เพิ่มตัวนับแบบ Atomic และรีเซ็ตเป็น 1 ทันทีเมื่อเปลี่ยนหน้าต่างเวลา"""
    now = timezone.now()
    window_start = now.replace(
        second=(now.second // window_seconds) * window_seconds
        if window_seconds < 60
        else 0,
        microsecond=0,
    )
    if window_seconds >= 60:
        minutes = window_seconds // 60
        window_start = window_start.replace(
            minute=(now.minute // minutes) * minutes
        )

    with transaction.atomic():
        bucket = (
            RateLimitBucket.objects.select_for_update()
            .filter(key=key)
            .first()
        )
        if bucket is None:
            try:
                with transaction.atomic():
                    RateLimitBucket.objects.create(
                        key=key, count=1, window_start=window_start
                    )
                    return 1
            except IntegrityError:
                bucket = RateLimitBucket.objects.select_for_update().get(
                    key=key
                )

        if bucket.window_start != window_start:
            RateLimitBucket.objects.filter(pk=bucket.pk).update(
                count=1, window_start=window_start
            )
            return 1

        RateLimitBucket.objects.filter(pk=bucket.pk).update(
            count=F("count") + 1
        )
        return bucket.count + 1


def rate_limit_feed(max_requests=40, window_seconds=60):
    """จำกัดความถี่การเรียก Feed/Search แบบ Atomic ป้องกัน Race Condition และ API Abuse"""

    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            ident = (
                f"user_{request.user.id}"
                if request.user.is_authenticated
                else f"ip_{request.META.get('REMOTE_ADDR', 'unknown')}"
            )
            is_search = bool(request.GET.get("q", "").strip())
            limit = 15 if is_search else max_requests
            bucket_key = f"rl_feed_{'search' if is_search else 'view'}_{ident}"

            count = _increment_rate_limit(bucket_key, window_seconds)
            if count > limit:
                return HttpResponse(
                    "Too Many Requests: กรุณารอสักครู่แล้วลองใหม่อีกครั้ง",
                    status=429,
                )
            return view_func(request, *args, **kwargs)

        return _wrapped_view

    return decorator


@rate_limit_feed(max_requests=40, window_seconds=60)
def home_view(request):
    context = get_feed_service().home_context(
        request.user,
        request.GET.get("q", ""),
        request.GET.get("saved") == "1",
    )
    return render(request, "home/home.html", context)


def explore_view(request):
    return home_view(request)


@login_required
@require_POST
def report_post_view(request, post_id):
    """รับการแจ้ง Report สแปม เฉพาะโพสต์ที่ผู้ใช้มีสิทธิ์มองเห็นเท่านั้น"""
    visible_posts = (
        Q(community__isnull=True)
        | Q(community__is_private=False)
        | Q(community__communitymember__user=request.user)
        | Q(community__owner=request.user)
    )
    post = get_object_or_404(Post.objects.filter(visible_posts).distinct(), pk=post_id)
    if post.user != request.user:
        SpamReport.objects.get_or_create(
            post=post,
            reporter=request.user,
            defaults={"reason": request.POST.get("reason", "Spam")[:255]},
        )
    return redirect(request.META.get("HTTP_REFERER", "/"))