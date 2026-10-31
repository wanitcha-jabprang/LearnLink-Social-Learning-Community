import json
from types import SimpleNamespace

from django.test import TestCase
from django.urls import reverse

from post.models import Bookmark, Comment, Like, Post
from post.views import MAX_VIDEO_SIZE, _validate_video
from users.models import User


class PostApiTests(TestCase):
    def setUp(self):
        self.author = User.objects.create_user(
            username="author",
            email="author@example.com",
            password="TestPassword123!",
            full_name="ผู้เขียน",
        )
        self.other_user = User.objects.create_user(
            username="other",
            email="other@example.com",
            password="TestPassword123!",
            full_name="ผู้ใช้อื่น",
        )
        self.post = Post.objects.create(user=self.author, content="เนื้อหาเดิม")

    def test_create_post_requires_login_and_persists(self):
        url = reverse("create_post")
        self.assertEqual(
            self.client.post(url, {"content": "โพสต์โดยไม่เข้าสู่ระบบ"}).status_code,
            401,
        )

        self.client.force_login(self.author)
        response = self.client.post(url, {"content": "  โพสต์ใหม่  "})

        self.assertEqual(response.status_code, 201)
        self.assertEqual(Post.objects.get(pk=response.json()["post"]["id"]).content, "โพสต์ใหม่")

    def test_only_author_can_edit_or_delete_post(self):
        self.client.force_login(self.other_user)
        edit_response = self.client.post(
            reverse("edit_post", args=[self.post.pk]),
            data=json.dumps({"content": "แก้โดยคนอื่น"}),
            content_type="application/json",
        )
        delete_response = self.client.post(reverse("delete_post", args=[self.post.pk]))

        self.assertEqual(edit_response.status_code, 403)
        self.assertEqual(delete_response.status_code, 403)
        self.post.refresh_from_db()
        self.assertEqual(self.post.content, "เนื้อหาเดิม")

        self.client.force_login(self.author)
        edit_response = self.client.post(
            reverse("edit_post", args=[self.post.pk]),
            data=json.dumps({"content": "  แก้แล้ว  "}),
            content_type="application/json",
        )
        self.assertEqual(edit_response.status_code, 200)
        self.assertEqual(edit_response.json()["post"]["content"], "แก้แล้ว")
        self.assertEqual(self.client.post(reverse("delete_post", args=[self.post.pk])).status_code, 200)
        self.assertFalse(Post.objects.filter(pk=self.post.pk).exists())

    def test_comment_create_edit_delete_checks_ownership(self):
        self.client.force_login(self.author)
        create_response = self.client.post(
            reverse("create_comment", args=[self.post.pk]),
            data=json.dumps({"content": "ความคิดเห็น"}),
            content_type="application/json",
        )
        self.assertEqual(create_response.status_code, 201)
        comment = Comment.objects.get(pk=create_response.json()["comment"]["id"])

        self.client.force_login(self.other_user)
        edit_response = self.client.post(
            reverse("edit_comment", args=[comment.pk]),
            data=json.dumps({"content": "แก้โดยคนอื่น"}),
            content_type="application/json",
        )
        self.assertEqual(edit_response.status_code, 403)
        self.assertEqual(self.client.post(reverse("delete_comment", args=[comment.pk])).status_code, 403)

        self.client.force_login(self.author)
        self.assertEqual(
            self.client.post(
                reverse("edit_comment", args=[comment.pk]),
                data=json.dumps({"content": "แก้ความคิดเห็น"}),
                content_type="application/json",
            ).status_code,
            200,
        )
        self.assertEqual(self.client.post(reverse("delete_comment", args=[comment.pk])).status_code, 200)
        self.assertFalse(Comment.objects.filter(pk=comment.pk).exists())

    def test_home_and_profile_render_database_posts(self):
        self.client.force_login(self.author)
        response = self.client.get(reverse("home"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "เนื้อหาเดิม")
        self.assertContains(response, "data-profile-post-list")
        self.assertEqual(list(response.context["profile_posts"]), [self.post])

    def test_video_upload_size_limit_is_enforced_by_server(self):
        oversized_video = SimpleNamespace(
            size=MAX_VIDEO_SIZE + 1,
            content_type="video/mp4",
        )
        self.assertEqual(_validate_video(oversized_video), "วิดีโอต้องมีขนาดไม่เกิน 100 MB")

    def test_like_and_bookmark_toggles_are_persisted_per_user(self):
        self.client.force_login(self.author)
        like_url = reverse("toggle_like", args=[self.post.pk])
        bookmark_url = reverse("toggle_bookmark", args=[self.post.pk])

        self.assertEqual(self.client.post(like_url).json(), {"liked": True})
        self.assertTrue(Like.objects.filter(post=self.post, user=self.author).exists())
        self.assertEqual(self.client.post(like_url).json(), {"liked": False})
        self.assertFalse(Like.objects.filter(post=self.post, user=self.author).exists())

        self.assertEqual(self.client.post(bookmark_url).json(), {"saved": True})
        self.assertTrue(Bookmark.objects.filter(post=self.post, user=self.author).exists())
        self.assertEqual(self.client.post(bookmark_url).json(), {"saved": False})
        self.assertFalse(Bookmark.objects.filter(post=self.post, user=self.author).exists())

    def test_html_post_forms_redirect_and_persist(self):
        self.client.force_login(self.author)
        response = self.client.post(
            reverse("create_post"),
            {"content": "โพสต์ผ่านฟอร์ม", "_html": "1", "next": "/#home-page"},
        )

        self.assertRedirects(response, "/#home-page", fetch_redirect_response=False)
        self.assertTrue(Post.objects.filter(user=self.author, content="โพสต์ผ่านฟอร์ม").exists())

    def test_saved_feed_filter_and_search_are_server_rendered(self):
        matching_post = Post.objects.create(user=self.other_user, content="Django สำหรับผู้เรียน")
        Post.objects.create(user=self.other_user, content="หัวข้ออื่น")
        Bookmark.objects.create(post=matching_post, user=self.author)
        self.client.force_login(self.author)

        saved_response = self.client.get(reverse("home"), {"saved": "1"})
        self.assertEqual(list(saved_response.context["posts"]), [matching_post])
        self.assertContains(saved_response, "โพสต์ที่บันทึกไว้")

        search_response = self.client.get(reverse("home"), {"q": "Django"})
        self.assertEqual(list(search_response.context["posts"]), [matching_post])
