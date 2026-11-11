from post.domain import policies


class PostAccessService:
    def __init__(self, posts):
        self.posts = posts

    def get_post(self, post_id):
        post = self.posts.get(post_id)
        if post is None:
            raise LookupError("ไม่พบโพสต์นี้")
        return post

    def can_access(self, user, post):
        community = post.community
        is_member = (
            self.posts.is_community_member(community, user)
            if community is not None
            else False
        )
        return policies.can_access(
            authenticated=user.is_authenticated,
            community_id=post.community_id,
            is_owner=community.owner_id == user.pk if community else False,
            is_member=is_member,
        )

    def require_access(self, user, post):
        if not self.can_access(user, post):
            raise PermissionError("คุณไม่มีสิทธิ์เข้าถึงโพสต์นี้")

    def require_community_membership(self, user, community):
        if (
            community.owner_id != user.pk
            and not self.posts.is_community_member(community, user)
        ):
            raise PermissionError("คุณต้องเข้าร่วมชุมชนก่อนจึงจะโพสต์ได้")


class PostService:
    def __init__(self, posts, upload_validation, access):
        self.posts = posts
        self.upload_validation = upload_validation
        self.access = access

    def create(
        self, user, *, content, image=None, video=None, community_id=None
    ):
        content = policies.normalize_content(content)
        error = self.upload_validation.validate_image(
            image
        ) or self.upload_validation.validate_video(video)
        if error:
            raise ValueError(error)

        community = None
        if community_id:
            community = self.posts.get_community(community_id)
            if community is None:
                raise LookupError("ไม่พบชุมชนนี้")
            self.access.require_community_membership(user, community)
        return self.posts.create(
            user=user,
            content=content,
            image=image,
            video=video,
            community=community,
        )

    def edit(self, post_id, user, content):
        post = self.access.get_post(post_id)
        if not policies.is_author(post.user_id, user.pk):
            raise PermissionError("คุณไม่มีสิทธิ์แก้ไขโพสต์นี้")
        post.content = policies.normalize_content(content)
        self.posts.save(post, ["content"])
        return post

    def delete(self, post_id, user):
        post = self.access.get_post(post_id)
        if not policies.is_author(post.user_id, user.pk):
            raise PermissionError("คุณไม่มีสิทธิ์ลบโพสต์นี้")
        self.posts.delete(post)

    def payload(self, post, comments_count):
        return {
            "id": post.pk,
            "content": post.content,
            "author": post.user.full_name or post.user.username,
            "community": post.community.name if post.community_id else "",
            "created_at": post.created_at.isoformat(),
            "image_url": post.image.url if post.image else "",
            "video_url": post.video.url if post.video else "",
            "likes_count": self.posts.count_likes(post),
            "comments_count": comments_count,
        }


class CommentService:
    def __init__(self, comments, access):
        self.comments = comments
        self.access = access

    def create(self, post_id, user, content):
        post = self.access.get_post(post_id)
        self.access.require_access(user, post)
        content = policies.normalize_content(content, "ความคิดเห็น")
        return self.comments.create(
            post=post, user=user, content=content
        ), post

    def edit(self, comment_id, user, content):
        comment = self.comments.get(comment_id)
        if comment is None:
            raise LookupError("ไม่พบความคิดเห็นนี้")
        self.access.require_access(user, comment.post)
        if not policies.is_author(comment.user_id, user.pk):
            raise PermissionError("คุณไม่มีสิทธิ์แก้ไขความคิดเห็นนี้")
        comment.content = policies.normalize_content(content, "ความคิดเห็น")
        self.comments.save(comment)
        return comment

    def delete(self, comment_id, user):
        comment = self.comments.get(comment_id)
        if comment is None:
            raise LookupError("ไม่พบความคิดเห็นนี้")
        self.access.require_access(user, comment.post)
        if not policies.is_author(comment.user_id, user.pk):
            raise PermissionError("คุณไม่มีสิทธิ์ลบความคิดเห็นนี้")
        self.comments.delete(comment)

    def count_for_post(self, post):
        return self.comments.count_for_post(post)


class PostInteractionService:
    def __init__(self, interactions, access):
        self.interactions = interactions
        self.access = access

    def toggle(self, kind, post_id, user):
        post = self.access.get_post(post_id)
        self.access.require_access(user, post)
        return self.interactions.toggle(kind, post, user)
