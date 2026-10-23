
from django.db.models import Q
from django.shortcuts import render

from community.models import Community, CommunityMember
from post.models import Bookmark, Like, Post
from users.models import Follow, User


def home_view(request):
    posts = Post.objects.select_related("user", "community").prefetch_related(
        "comment_set__user",
        "like_set",
    ).order_by("-created_at")

    if request.user.is_authenticated:
        posts = posts.filter(
            Q(community__isnull=True)
            | Q(community__is_private=False)
            | Q(community__communitymember__user=request.user)
            | Q(community__owner=request.user)
        ).distinct()
    else:
        posts = posts.filter(
            Q(community__isnull=True)
            | Q(community__is_private=False)
        )

    query = request.GET.get("q", "").strip()
    searched_communities = Community.objects.none()
    if query:
        search_term = query.removeprefix("#").strip()
        
        # ค้นหาโพสต์จาก: เนื้อหาโพสต์ | ชื่อจริงผู้โพสต์ | username ผู้โพสต์ | ชื่อ Community
        posts = posts.filter(
            Q(content__icontains=search_term)
            | Q(user__full_name__icontains=search_term)
            | Q(user__username__icontains=search_term)
            | Q(community__name__icontains=search_term)
        ).distinct()

        # ค้นหา Community ตามชื่อหรือรายละเอียด เพื่อนำไปแสดงในผลการค้นหาเพิ่มเติม
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

    # รายชื่อผู้เรียนที่แนะนำ โดยไม่แสดงบัญชีตัวเอง
    suggested_users = (
        User.objects.exclude(pk=request.user.pk).order_by("-created_at")[:5]
        if request.user.is_authenticated
        else User.objects.none()
    )

    # ID ของผู้ใช้ที่บัญชีปัจจุบันติดตามอยู่
    followed_user_ids = (
        set(
            Follow.objects.filter(follower=request.user)
            .values_list("following_id", flat=True)
        )
        if request.user.is_authenticated
        else set()
    )

    return render(
        request,
        "home/home.html",
        {
            "posts": posts,
            "profile_posts": profile_posts,
            "liked_post_ids": liked_post_ids,
            "saved_post_ids": saved_post_ids,
            "search_query": query,
            "searched_communities": searched_communities,
            "saved_only": saved_only,
            "communities": communities.order_by("name"),
            "suggested_users": suggested_users,
            "followed_user_ids": followed_user_ids,
            "joined_communities": (
                Community.objects.filter(
                    Q(communitymember__user=request.user)
                    | Q(owner=request.user)
                )
                .distinct()
                .order_by("name")
                if request.user.is_authenticated
                else []
            ),
            "joined_community_ids": (
                set(
                    Community.objects.filter(
                        Q(communitymember__user=request.user)
                        | Q(owner=request.user)
                    ).values_list("pk", flat=True)
                )
                if request.user.is_authenticated
                else set()
            ),
        },
    )


def explore_view(request):
    return render(request, "home/explore.html")