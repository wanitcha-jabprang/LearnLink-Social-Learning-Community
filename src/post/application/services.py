from post.domain import policies


class PostService:
    def __init__(self, posts, comments, interactions, upload_validation):
        self.posts = posts
        self.comments = comments
        self.interactions = interactions
        self.upload_validation = upload_validation

    def _get_post(self, post_id):
        post = self.posts.get(post_id)
        if post is None:
            raise LookupError("ไม่พบโพสต์นี้")
        return post

    def _can_access(self, user, post):
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

    def create(self, user, *, content, image=None, video=None, community_id=None):
        content = policies.normalize_content(content)
        error = self.upload_validation.validate_image(image) or self.upload_validation.validate_video(video)
        if error:
            raise ValueError(error)
        community = None
        if community_id:
            community = self.posts.get_community(community_id)
            if community is None:
                raise LookupError("ไม่พบชุมชนนี้")
            if (
                community.owner_id != user.pk
                and not self.posts.is_community_member(community, user)
            ):
                raise PermissionError("คุณต้องเข้าร่วมชุมชนก่อนจึงจะโพสต์ได้")
        return self.posts.create(
            user=user,
            content=content,
            image=image,
            video=video,
            community=community,
        )

    def edit(self, post_id, user, content):
        post = self._get_post(post_id)
        if not policies.is_author(post.user_id, user.pk):
            raise PermissionError("คุณไม่มีสิทธิ์แก้ไขโพสต์นี้")
        post.content = policies.normalize_content(content)
        self.posts.save(post, ["content"])
        return post

    def delete(self, post_id, user):
        post = self._get_post(post_id)
        if not policies.is_author(post.user_id, user.pk):
            raise PermissionError("คุณไม่มีสิทธิ์ลบโพสต์นี้")
        self.posts.delete(post)

    def create_comment(self, post_id, user, content):
        post = self._get_post(post_id)
        if not self._can_access(user, post):
            raise PermissionError("คุณไม่มีสิทธิ์เข้าถึงโพสต์นี้")
        content = policies.normalize_content(content, "ความคิดเห็น")
        return self.comments.create(post=post, user=user, content=content), post

    def edit_comment(self, comment_id, user, content):
        comment = self.comments.get(comment_id)
        if comment is None:
            raise LookupError("ไม่พบความคิดเห็นนี้")
        if not self._can_access(user, comment.post):
            raise PermissionError("คุณไม่มีสิทธิ์เข้าถึงโพสต์นี้")
        if not policies.is_author(comment.user_id, user.pk):
            raise PermissionError("คุณไม่มีสิทธิ์แก้ไขความคิดเห็นนี้")
        comment.content = policies.normalize_content(content, "ความคิดเห็น")
        self.comments.save(comment)
        return comment

    def delete_comment(self, comment_id, user):
        comment = self.comments.get(comment_id)
        if comment is None:
            raise LookupError("ไม่พบความคิดเห็นนี้")
        if not self._can_access(user, comment.post):
            raise PermissionError("คุณไม่มีสิทธิ์เข้าถึงโพสต์นี้")
        if not policies.is_author(comment.user_id, user.pk):
            raise PermissionError("คุณไม่มีสิทธิ์ลบความคิดเห็นนี้")
        self.comments.delete(comment)

    def toggle(self, kind, post_id, user):
        post = self._get_post(post_id)
        if not self._can_access(user, post):
            raise PermissionError("คุณไม่มีสิทธิ์เข้าถึงโพสต์นี้")
        return self.interactions.toggle(kind, post, user)

    def post_payload(self, post):
        return {
            "id": post.pk,
            "content": post.content,
            "author": post.user.full_name or post.user.username,
            "community": post.community.name if post.community_id else "",
            "created_at": post.created_at.isoformat(),
            "image_url": post.image.url if post.image else "",
            "video_url": post.video.url if post.video else "",
            "likes_count": self.posts.count_likes(post),
            "comments_count": self.comments.count_for_post(post),
        }
