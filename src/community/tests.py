from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse

from community.infrastructure.container import get_community_service
from community.infrastructure.persistence.models import (
    Community,
    CommunityMember,
)
from post.infrastructure.persistence.models import Post
from users.infrastructure.persistence.models import User


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
        self.assertTrue(
            CommunityMember.objects.filter(
                community=community, user=self.owner
            ).exists()
        )
        self.assertEqual(len(community.invite_code), 8)

        self.client.force_login(self.member)
        join_url = reverse("join_community", args=[community.pk])
        self.client.post(join_url, {"invite_code": "WRONG"})
        self.assertFalse(
            CommunityMember.objects.filter(
                community=community, user=self.member
            ).exists()
        )
        self.client.post(
            join_url, {"invite_code": community.invite_code.lower()}
        )
        self.assertTrue(
            CommunityMember.objects.filter(
                community=community, user=self.member
            ).exists()
        )

    def test_public_community_can_be_joined_and_left(self):
        community = Community.objects.create(
            name="สาธารณะ",
            description="",
            invite_code="PUBLIC22",
            owner=self.owner,
        )
        self.client.force_login(self.member)

        self.client.post(reverse("join_community", args=[community.pk]))
        self.assertTrue(
            CommunityMember.objects.filter(
                community=community, user=self.member
            ).exists()
        )
        self.client.post(reverse("leave_community", args=[community.pk]))
        self.assertFalse(
            CommunityMember.objects.filter(
                community=community, user=self.member
            ).exists()
        )

    def test_join_rejects_none_invite_code(self):
        community = Community.objects.create(
            name="ชุมชนส่วนตัว",
            description="",
            invite_code="PRIVATE2",
            is_private=True,
            owner=self.owner,
        )

        with self.assertRaisesRegex(ValueError, "รหัสเชิญไม่ถูกต้อง"):
            get_community_service().join(community.pk, self.member, None)

    def test_update_saves_only_fields_that_were_updated(self):
        community = Community.objects.create(
            name="ชุมชนเดิม",
            description="รายละเอียดเดิม",
            invite_code="COMMUNITY",
            owner=self.owner,
        )
        service = get_community_service()

        with patch.object(service.communities, "save") as save:
            service.update(
                community.pk,
                self.owner,
                name="ชุมชนใหม่",
                description="รายละเอียดใหม่",
                image=None,
                is_private=True,
            )

        save.assert_called_once()
        self.assertEqual(
            save.call_args.kwargs["fields"],
            ["name", "description", "is_private"],
        )

    def test_community_image_validation_runs_in_service(self):
        service = get_community_service()
        with patch.object(
            service.image_validation,
            "validate_image",
            return_value="ไฟล์รูปภาพไม่ถูกต้อง",
        ):
            with self.assertRaisesRegex(ValueError, "ไฟล์รูปภาพไม่ถูกต้อง"):
                service.create(
                    name="ชุมชนใหม่",
                    description="",
                    image=object(),
                    is_private=False,
                    owner=self.owner,
                )

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
            self.client.post(
                reverse("toggle_like", args=[private_post.pk])
            ).status_code,
            404,
        )
        self.assertEqual(
            self.client.post(
                reverse("create_comment", args=[private_post.pk]),
                {"content": "แอบอ่าน"},
            ).status_code,
            404,
        )
