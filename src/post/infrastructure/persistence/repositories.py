from community.infrastructure.persistence.models import (
    Community,
    CommunityMember,
)
from post.infrastructure.persistence.models import (
    Bookmark,
    Comment,
    Like,
    Post,
)


class PostRepository:
    def get(self, post_id):
        return (
            Post.objects.filter(pk=post_id)
            .select_related("user", "community")
            .first()
        )

    def get_community(self, community_id):
        return Community.objects.filter(pk=community_id).first()

    def is_community_member(self, community, user):
        return CommunityMember.objects.filter(
            community=community, user=user
        ).exists()

    def create(self, **values):
        return Post.objects.create(**values)

    def save(self, instance, fields=None):
        instance.save(update_fields=fields)

    def delete(self, post):
        media = (post.image, post.video)
        post.delete()
        for file in media:
            if file:
                file.delete(save=False)

    def count_likes(self, post):
        return post.like_set.count()


class CommentRepository:
    def get(self, comment_id):
        return (
            Comment.objects.filter(pk=comment_id)
            .select_related("user", "post__community")
            .first()
        )

    def create(self, **values):
        return Comment.objects.create(**values)

    def save(self, comment):
        comment.save(update_fields=["content"])

    def delete(self, comment):
        comment.delete()

    def count_for_post(self, post):
        return post.comment_set.count()


class InteractionRepository:
    def _model_for(self, kind):
        return Like if kind == "like" else Bookmark

    def toggle(self, kind, post, user):
        model = self._model_for(kind)
        instance, created = model.objects.get_or_create(post=post, user=user)
        if not created:
            instance.delete()
        return created
