from functools import wraps

from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from feed.infrastructure.container import get_feed_service
from feed.infrastructure.persistence.models import SpamReport
from post.infrastructure.persistence.models import Post


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
            cache_key = f"rl_feed_{'search' if is_search else 'view'}_{ident}"

            # ใช้ cache.add และ cache.incr เพื่อให้การนับเป็น Atomic ปลอดภัยต่อ Multi-worker
            if cache.add(cache_key, 1, timeout=window_seconds):
                count = 1
            else:
                try:
                    count = cache.incr(cache_key)
                except ValueError:
                    cache.set(cache_key, 1, timeout=window_seconds)
                    count = 1

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
    response = render(request, "home/home.html", context)
    response["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self'; "
        "style-src 'self' https://fonts.googleapis.com; "
        "img-src 'self' data: blob: https:; "
        "font-src 'self' https://fonts.gstatic.com data:;"
    )
    return response


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