from django.db.models import Q

from community.infrastructure.persistence.models import Community
from post.infrastructure.persistence.models import Bookmark, Like, Post
from users.infrastructure.persistence.models import Follow, User


class FeedRepository:
    def home_context(self, user, query, saved_only):
        posts = (
            Post.objects.filter(is_hidden=False)
            .select_related("user", "community")
            .prefetch_related("comment_set__user", "like_set")
            .order_by("-created_at")
        )
        visible_posts = (
            Q(community__isnull=True)
            | Q(community__is_private=False)
            | Q(community__communitymember__user=user)
            | Q(community__owner=user)
        )
        posts = (
            posts.filter(visible_posts).distinct()
            if user.is_authenticated
            else posts.filter(
                Q(community__isnull=True) | Q(community__is_private=False)
            )
        )

        searched_communities = Community.objects.none()
        if query:
            posts = posts.filter(
                Q(content__icontains=query)
                | Q(user__full_name__icontains=query)
                | Q(user__username__icontains=query)
                | Q(community__name__icontains=query)
            ).distinct()
            searched_communities = Community.objects.filter(
                Q(name__icontains=query) | Q(description__icontains=query)
            )
            searched_communities = (
                searched_communities.filter(
                    Q(is_private=False)
                    | Q(communitymember__user=user)
                    | Q(owner=user)
                ).distinct()
                if user.is_authenticated
                else searched_communities.filter(is_private=False)
            )

        if saved_only:
            posts = (
                posts.filter(bookmarks__user=user)
                if user.is_authenticated
                else posts.none()
            )

        profile_posts = (
            Post.objects.filter(user=user, is_hidden=False)
            .select_related("user", "community")
            .prefetch_related("comment_set__user", "like_set")
            .order_by("-created_at")
            if user.is_authenticated
            else []
        )
        communities = Community.objects.all()
        communities = (
            communities.filter(
                Q(is_private=False)
                | Q(communitymember__user=user)
                | Q(owner=user)
            ).distinct()
            if user.is_authenticated
            else communities.filter(is_private=False)
        )
        if user.is_authenticated:
            joined_communities = Community.objects.filter(
                Q(communitymember__user=user) | Q(owner=user)
            ).distinct()
            joined_community_ids = set(
                joined_communities.values_list("pk", flat=True)
            )
            liked_post_ids = set(
                Like.objects.filter(user=user).values_list(
                    "post_id", flat=True
                )
            )
            saved_post_ids = set(
                Bookmark.objects.filter(user=user).values_list(
                    "post_id", flat=True
                )
            )
            followed_user_ids = set(
                Follow.objects.filter(follower=user).values_list(
                    "following_id", flat=True
                )
            )
            suggested_users = User.objects.exclude(pk=user.pk).order_by(
                "-created_at"
            )[:5]
        else:
            joined_communities = []
            joined_community_ids = set()
            liked_post_ids = set()
            saved_post_ids = set()
            followed_user_ids = set()
            suggested_users = User.objects.none()

        return {
            "posts": posts,
            "profile_posts": profile_posts,
            "liked_post_ids": liked_post_ids,
            "saved_post_ids": saved_post_ids,
            "search_query": query,
            "searched_communities": searched_communities,
            "saved_only": saved_only,
            "communities": communities.order_by("name"),
            "joined_communities": joined_communities,
            "joined_community_ids": joined_community_ids,
            "followed_user_ids": followed_user_ids,
            "suggested_users": suggested_users,
        }