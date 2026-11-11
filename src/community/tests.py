<<<<<<< HEAD
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
=======
import tempfile
from io import BytesIO
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from PIL import Image

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

    def test_create_community_with_valid_image(self):
        image_file = BytesIO()
        Image.new("RGB", (4, 4), color="blue").save(
            image_file,
            format="PNG",
        )
        image = SimpleUploadedFile(
            "community.png",
            image_file.getvalue(),
            content_type="image/png",
        )

        with tempfile.TemporaryDirectory() as media_root:
            with override_settings(MEDIA_ROOT=media_root):
                community = get_community_service().create(
                    name="ชุมชนพร้อมภาพ",
                    description="",
                    image=image,
                    is_private=False,
                    owner=self.owner,
                )

                self.assertTrue(community.image.name.endswith(".png"))
                self.assertTrue(
                    community.image.storage.exists(community.image.name)
                )

    def test_create_community_without_image(self):
        community = get_community_service().create(
            name="ชุมชนไม่มีภาพ",
            description="",
            image=None,
            is_private=False,
            owner=self.owner,
        )

        self.assertFalse(community.image)

    def test_create_community_rejects_corrupted_image(self):
        image = SimpleUploadedFile(
            "corrupted.png",
            b"not a valid image",
            content_type="image/png",
        )

        with self.assertRaisesRegex(ValueError, "ไฟล์รูปภาพไม่ถูกต้อง"):
            get_community_service().create(
                name="ชุมชนรูปเสีย",
                description="",
                image=image,
                is_private=False,
                owner=self.owner,
            )

        self.assertFalse(Community.objects.filter(name="ชุมชนรูปเสีย").exists())

    def test_update_without_new_image_preserves_existing_image(self):
        image_file = BytesIO()
        Image.new("RGB", (4, 4), color="green").save(
            image_file,
            format="PNG",
        )
        image = SimpleUploadedFile(
            "existing.png",
            image_file.getvalue(),
            content_type="image/png",
        )

        with tempfile.TemporaryDirectory() as media_root:
            with override_settings(MEDIA_ROOT=media_root):
                community = Community.objects.create(
                    name="ชุมชนเดิม",
                    description="รายละเอียดเดิม",
                    invite_code="COMMUNITY",
                    owner=self.owner,
                    image=image,
                )
                original_image_name = community.image.name

                updated_community = get_community_service().update(
                    community.pk,
                    self.owner,
                    name="ชื่อใหม่",
                    description="คำอธิบายใหม่",
                    image=None,
                    is_private=False,
                )
                updated_community.refresh_from_db()

                self.assertEqual(updated_community.name, "ชื่อใหม่")
                self.assertEqual(updated_community.description, "คำอธิบายใหม่")
                self.assertEqual(
                    updated_community.image.name, original_image_name
                )
                self.assertTrue(
                    updated_community.image.storage.exists(original_image_name)
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
>>>>>>> origin/develop
