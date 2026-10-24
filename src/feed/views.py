from django.db.models import Q
from django.shortcuts import render

from community.models import Community
from post.models import Bookmark, Like, Post
from users.models import Follow, User


def home_view(request):
    # 1. ดึงโพสต์ทั้งหมด
    posts = (
        Post.objects.select_related("user", "community")
        .prefetch_related("comment_set__user", "like_set")
        .order_by("-created_at")
    )

    # 2. กรองโพสต์ตามสิทธิ์การเข้าถึงชุมชน
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

    # 3. ค้นหาโพสต์
    query = request.GET.get("q", "").strip()

    if query:
        search_term = query.removeprefix("#").strip()
        posts = posts.filter(
            Q(content__icontains=search_term)
            | Q(user__full_name__icontains=search_term)
            | Q(user__username__icontains=search_term)
            | Q(community__name__icontains=search_term)
        )

    # 4. แสดงเฉพาะโพสต์ที่บันทึกไว้ หากมีการร้องขอ
    saved_only = request.GET.get("saved") == "1"

    if saved_only and request.user.is_authenticated:
        posts = posts.filter(bookmarks__user=request.user)
    elif saved_only:
        posts = posts.none()

    # 5. ดึงโพสต์ของผู้ใช้ปัจจุบัน
    profile_posts = (
        Post.objects.filter(user=request.user)
        .select_related("user", "community")
        .prefetch_related("comment_set__user", "like_set")
        .order_by("-created_at")
        if request.user.is_authenticated
        else []
    )

    # 6. เก็บ ID โพสต์ที่กดถูกใจหรือบันทึกไว้
    liked_post_ids = set()
    saved_post_ids = set()

    if request.user.is_authenticated:
        liked_post_ids = set(
            Like.objects.filter(user=request.user).values_list(
                "post_id", flat=True
            )
        )

        saved_post_ids = set(
            Bookmark.objects.filter(user=request.user).values_list(
                "post_id", flat=True
            )
        )

    # 7. ดึงชุมชนที่ผู้ใช้มีสิทธิ์เข้าถึง
    communities = Community.objects.all()

    if request.user.is_authenticated:
        communities = communities.filter(
            Q(is_private=False)
            | Q(communitymember__user=request.user)
            | Q(owner=request.user)
        ).distinct()
    else:
        communities = communities.filter(is_private=False)

    # 8. ดึงชุมชนที่ผู้ใช้เข้าร่วม
    joined_communities = (
        Community.objects.filter(
            Q(communitymember__user=request.user)
            | Q(owner=request.user)
        ).distinct()
        if request.user.is_authenticated
        else Community.objects.none()
    )

    # 9. แนะนำผู้ใช้ โดยไม่แสดงบัญชีตัวเอง
    suggested_users = (
        User.objects.exclude(pk=request.user.pk).order_by("-created_at")[:5]
        if request.user.is_authenticated
        else User.objects.none()
    )

    # 10. เก็บ ID ของผู้ใช้ที่บัญชีปัจจุบันติดตามอยู่
    followed_user_ids = (
        set(
            Follow.objects.filter(follower=request.user).values_list(
                "following_id", flat=True
            )
        )
        if request.user.is_authenticated
        else set()
    )

    # 11. ส่งข้อมูลไปยัง Template
    context = {
        "posts": posts,
        "query": query,
        "search_query": query,
        "saved_only": saved_only,
        "profile_posts": profile_posts,
        "liked_post_ids": liked_post_ids,
        "saved_post_ids": saved_post_ids,
        "communities": communities,
        "joined_communities": joined_communities,
        "suggested_users": suggested_users,
        "followed_user_ids": followed_user_ids,
    }

    return render(request, "home/home.html", context)


def explore_view(request):
    # ใช้หน้าเดียวกับ Home เพื่อให้ URL /explore/ ทำงานได้
    return home_view(request)

def home_view(request):
    posts = Post.objects.select_related("user", "community").prefetch_related(
        "comment_set__user",
        "like_set",
    ).order_by("-created_at")
    
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


def explore_view(request):
    return render(request, "home/explore.html")
