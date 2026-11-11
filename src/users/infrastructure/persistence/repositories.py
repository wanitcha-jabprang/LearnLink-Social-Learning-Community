from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.db.models import Q

from community.infrastructure.persistence.models import Community, CommunityMember
from post.infrastructure.persistence.models import Post
from users.infrastructure.persistence.models import Follow


class UserRepository:
    @property
    def model(self):
        return get_user_model()

    def get(self, user_id):
        return self.model.objects.filter(pk=user_id).first()

    def find_by_email(self, email):
        return self.model.objects.filter(email__iexact=email).first()

    def username_exists(self, username):
        return self.model.objects.filter(username__iexact=username).exists()

    def email_exists(self, email):
        return self.model.objects.filter(email__iexact=email).exists()

    def create(self, **values):
        return self.model.objects.create_user(**values)

    def clean_username(self, username):
        return self.model._meta.get_field("username").clean(username, None)

    def validate_password(self, username, full_name, email, password):
        user = self.model(username=username, full_name=full_name, email=email)
        validate_password(password, user)

    def username_exists_for_other_user(self, username, user_id):
        return self.model.objects.filter(username__iexact=username).exclude(
            pk=user_id
        ).exists()

    def save(self, user, fields=None):
        user.save(update_fields=fields)


class FollowRepository:
    def is_following(self, follower, following):
        return Follow.objects.filter(
            follower=follower, following=following
        ).exists()

    def add(self, follower, following):
        return Follow.objects.get_or_create(follower=follower, following=following)

    def remove(self, follower, following):
        return Follow.objects.filter(
            follower=follower, following=following
        ).delete()[0]


class UserProfileRepository:
    def visible_posts(self, profile_user, viewer):
        posts = Post.objects.filter(user=profile_user).filter(
            Q(community__isnull=True)
            | Q(community__is_private=False)
            | Q(community__communitymember__user=viewer)
            | Q(community__owner=viewer)
        )
        return (
            posts.select_related("user", "community")
            .prefetch_related("comment_set__user", "like_set")
            .distinct()
            .order_by("-created_at")
        )

    def profile_counts(self, profile_user, posts):
        return {
            "followers_count": profile_user.followers.count(),
            "following_count": profile_user.following.count(),
            "posts_count": posts.count(),
        }


class AccountDeletionRepository:
    def owned_communities(self, user):
        return Community.objects.filter(owner=user)

    def successor(self, community, departing_user):
        membership = (
            CommunityMember.objects.filter(community=community)
            .exclude(user=departing_user)
            .select_related("user")
            .order_by("joined_at", "pk")
            .first()
        )
        return membership.user if membership else None

    def transfer_owner(self, community, new_owner):
        community.owner = new_owner
        community.save(update_fields=["owner"])

    def delete_communities(self, communities):
        for community in communities:
            community.delete()

    def media_for_deletion(self, user, communities_to_delete):
        media = []
        for field in (user.profile_image, user.profile_cover):
            if field:
                media.append((field.storage, field.name))

        posts = Post.objects.filter(user=user) | Post.objects.filter(
            community__in=communities_to_delete
        )
        for post in posts.distinct().only("image", "video"):
            for field in (post.image, post.video):
                if field:
                    media.append((field.storage, field.name))

        for community in communities_to_delete:
            if community.image:
                media.append((community.image.storage, community.image.name))
        return media

    def delete_user(self, user):
        user.delete()
