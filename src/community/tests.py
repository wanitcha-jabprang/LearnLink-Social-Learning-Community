from django.test import TestCase
from django.urls import reverse

from community.models import Community, CommunityMember
from post.models import Post
from users.models import User


class CommunityWorkflowTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            username="owner",
            email="owner@example.com",
            password="StrongPass123!",
            full_name="เจ้าของ",
        )
        self.member = User.objects.create_user(
            username="member",
            email="member@example.com",
            password="StrongPass123!",
            full_name="สมาชิก",
        )

    def test_create_and_join_private_community_requires_invite_code(self):
        self.client.force_login(self.owner)
        response = self.client.post(
            reverse("create_community"),
            {
                "name": "ชุมชน Python",
                "description": "เรียน Python ด้วยกัน",
                "is_private": "true",
            },
        )
        community = Community.objects.get(name="ชุมชน Python")

        self.assertRedirects(
            response,
            f"/#community-{community.pk}",
            fetch_redirect_response=False,
        )
        self.assertTrue(CommunityMember.objects.filter(community=community, user=self.owner).exists())
        self.assertEqual(len(community.invite_code), 8)

        self.client.force_login(self.member)
        join_url = reverse("join_community", args=[community.pk])
        self.client.post(join_url, {"invite_code": "WRONG"})
        self.assertFalse(CommunityMember.objects.filter(community=community, user=self.member).exists())
        self.client.post(join_url, {"invite_code": community.invite_code.lower()})
        self.assertTrue(CommunityMember.objects.filter(community=community, user=self.member).exists())

    def test_public_community_can_be_joined_and_left(self):
        community = Community.objects.create(
            name="สาธารณะ",
            description="",
            invite_code="PUBLIC22",
            owner=self.owner,
        )
        self.client.force_login(self.member)

        self.client.post(reverse("join_community", args=[community.pk]))
        self.assertTrue(CommunityMember.objects.filter(community=community, user=self.member).exists())
        self.client.post(reverse("leave_community", args=[community.pk]))
        self.assertFalse(CommunityMember.objects.filter(community=community, user=self.member).exists())

    def test_community_hub_is_rendered_from_database(self):
        community = Community.objects.create(
            name="Python",
            description="เรียนรู้ร่วมกัน",
            invite_code="PYTHON22",
            owner=self.owner,
        )
        CommunityMember.objects.create(community=community, user=self.owner)
        self.client.force_login(self.owner)

        response = self.client.get(reverse("home"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Python")
        self.assertContains(response, community.invite_code)
        self.assertContains(response, f"community-{community.pk}")

    def test_private_community_is_not_visible_before_joining(self):
        community = Community.objects.create(
            name="ชุมชนส่วนตัว",
            description="เฉพาะสมาชิก",
            invite_code="PRIVATE2",
            is_private=True,
            owner=self.owner,
        )
        private_post = Post.objects.create(
            user=self.owner,
            community=community,
            content="เฉพาะสมาชิกเท่านั้น",
        )
        self.client.force_login(self.member)

        response = self.client.get(reverse("home"))

        self.assertNotContains(response, community.name)
        self.assertNotContains(response, private_post.content)
        self.assertEqual(
            self.client.post(reverse("toggle_like", args=[private_post.pk])).status_code,
            404,
        )
        self.assertEqual(
            self.client.post(reverse("create_comment", args=[private_post.pk]), {"content": "แอบอ่าน"}).status_code,
            404,
        )

    def test_community_posts_are_only_shown_to_members_in_feed(self):
        community = Community.objects.create(
            name="ชุมชนสาธารณะ",
            description="โพสต์สำหรับสมาชิก",
            invite_code="PUBLIC22",
            owner=self.owner,
        )
        post = Post.objects.create(
            user=self.owner,
            community=community,
            content="โพสต์ในกลุ่มที่ยังไม่ได้เข้าร่วม",
        )
        feed_url = reverse("home")

        self.assertNotContains(self.client.get(feed_url), post.content)

        self.client.force_login(self.member)
        self.assertNotContains(self.client.get(feed_url), post.content)

        self.client.post(reverse("join_community", args=[community.pk]))
        self.assertContains(self.client.get(feed_url), post.content)
