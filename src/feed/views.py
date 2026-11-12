from django.contrib.auth.decorators import login_required
from django.db.models import Count
from django.shortcuts import get_object_or_404, redirect
from django.views.decorators.http import require_POST
from .models import SpamReport
from django.db.models import Q
from django.shortcuts import render
from django.utils.html import escape
from community.models import Community, CommunityMember
from post.models import Bookmark, Like, Post

from functools import wraps
from django.core.cache import cache
from django.http import HttpResponse


def rate_limit_feed(max_requests=40, window_seconds=60):
    """จำกัดความถี่การเรียก Feed/Search ป้องกัน Bot และ API Abuse"""
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

            count = cache.get(cache_key, 0)
            if count >= limit:
                return HttpResponse(
                    "Too Many Requests: กรุณารอสักครู่แล้วลองใหม่อีกครั้ง",
                    status=429,
                )
            cache.set(cache_key, count + 1, timeout=window_seconds)
            return view_func(request, *args, **kwargs)
        return _wrapped_view
    return decorator
@rate_limit_feed(max_requests=40, window_seconds=60)
def home_view(request):
    posts = (
        Post.objects.select_related("user", "community")
        .annotate(report_count=Count("spam_reports"))
        .filter(report_count__lt=3)  # Auto Hide สแปมที่โดน Report ตั้งแต่ 3 ครั้งขึ้นไป
        .only(
            "id", "content", "image", "video", "created_at", "community_id",
            "user__id", "user__username", "user__full_name", "user__profile_image",
            "community__id", "community__name", "community__is_private", "community__owner_id",
        )
        .prefetch_related("comment_set__user", "like_set")
        .order_by("-created_at")
    )
    
    # คัดกรองโพสต์ตามสิทธิ์การมองเห็น
    if request.user.is_authenticated:
        posts = posts.filter(
            Q(community__isnull=True)
            | Q(community__is_private=False)
            | Q(community__communitymember__user=request.user)
            | Q(community__owner=request.user)
        ).distinct()
    else:
        posts = posts.filter(
            Q(community__isnull=True) | Q(community__is_private=False)
        )
        
    query = request.GET.get("q", "").strip()
    searched_communities = Community.objects.none()

    if query:
        search_term = query.removeprefix("#").strip()
        
        # ค้นหาโพสต์: เนื้อหา | ชื่อผู้ใช้ | username | ชื่อกลุ่ม
        posts = posts.filter(
            Q(content__icontains=search_term)
            | Q(user__full_name__icontains=search_term)
            | Q(user__username__icontains=search_term)
            | Q(community__name__icontains=search_term)
        ).distinct()

        # ค้นหากลุ่ม (Community) โดยตรง
        searched_communities = Community.objects.filter(
            Q(name__icontains=search_term) | Q(description__icontains=search_term)
        )
        if request.user.is_authenticated:
            searched_communities = searched_communities.filter(
                Q(is_private=False)
                | Q(communitymember__user=request.user)
                | Q(owner=request.user)
            ).distinct()
        else:
            searched_communities = searched_communities.filter(is_private=False)

    saved_only = request.GET.get("saved") == "1"
    if saved_only and request.user.is_authenticated:
        posts = posts.filter(bookmarks__user=request.user)
    elif saved_only:
        posts = posts.none()
        
    profile_posts = (
        Post.objects.filter(user=request.user)
        .select_related("user", "community")
        .prefetch_related("comment_set__user", "like_set")
        .order_by("-created_at")
        if request.user.is_authenticated
        else []
    )
    
    liked_post_ids = set()
    saved_post_ids = set()
    if request.user.is_authenticated:
        liked_post_ids = set(
            Like.objects.filter(user=request.user).values_list("post_id", flat=True)
        )
        saved_post_ids = set(
            Bookmark.objects.filter(user=request.user).values_list("post_id", flat=True)
        )
        
    communities = Community.objects.all()
    if request.user.is_authenticated:
        communities = communities.filter(
            Q(is_private=False)
            | Q(communitymember__user=request.user)
            | Q(owner=request.user)
        ).distinct()
    else:
        communities = communities.filter(is_private=False)
        
    response = render(
        request,
        "home/home.html",
        {
            "posts": posts,
            "profile_posts": profile_posts,
            "liked_post_ids": liked_post_ids,
            "saved_post_ids": saved_post_ids,
            "search_query": escape(query),
            "searched_communities": searched_communities,
            "saved_only": saved_only,
            "communities": communities.order_by("name"),
            "joined_communities": (
                Community.objects.filter(
                    Q(communitymember__user=request.user) | Q(owner=request.user)
                )
                .distinct()
                .order_by("name")
                if request.user.is_authenticated
                else []
            ),
            "joined_community_ids": (
                set(
                    Community.objects.filter(
                        Q(communitymember__user=request.user) | Q(owner=request.user)
                    ).values_list("pk", flat=True)
                )
                if request.user.is_authenticated
                else set()
           ),
        },
    )
    response["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' https://cdn.tailwindcss.com https://unpkg.com; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
        "img-src 'self' data: blob: https:; "
        "font-src 'self' https://fonts.gstatic.com data:;"
    )
    return response

@rate_limit_feed(max_requests=40, window_seconds=60)
def explore_view(request):
    return render(request, "home/explore.html")
@rate_limit_feed(max_requests=40, window_seconds=60)
def explore_view(request):
    return render(request, "home/explore.html")


@login_required
@require_POST
def report_post_view(request, post_id):
    """รับการแจ้ง Report สแปม และ Auto Hide อัตโนมัติเมื่อถึงเกณฑ์"""
    post = get_object_or_404(Post, pk=post_id)
    if post.user != request.user:
        SpamReport.objects.get_or_create(
            post=post,
            reporter=request.user,
            defaults={"reason": request.POST.get("reason", "Spam")[:255]},
        )
    return redirect(request.META.get("HTTP_REFERER", "/"))