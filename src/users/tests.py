import tempfile
from io import BytesIO

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.test import TestCase
from django.urls import reverse
from PIL import Image

from community.models import Community, CommunityMember
from post.models import Post
from users.models import User


class AuthenticationFlowTests(TestCase):
    def test_registration_creates_and_logs_in_user(self):
        response = self.client.post(
            reverse("register"),
            {
                "full_name": "ผู้เรียนใหม่",
                "username": "my-chosen-name",
                "email": "new.learner@example.com",
                "password": "StrongPass123!",
            },
        )

        self.assertRedirects(response, reverse("home"))
        user = User.objects.get(email="new.learner@example.com")
        self.assertEqual(user.full_name, "ผู้เรียนใหม่")
        self.assertEqual(user.username, "my-chosen-name")
        self.assertTrue(user.check_password("StrongPass123!"))
        self.assertIn("_auth_user_id", self.client.session)

    def test_registration_rejects_duplicate_username_case_insensitively(self):
        User.objects.create_user(
            username="ExistingUser",
            email="existing@example.com",
            password="StrongPass123!",
            full_name="ผู้เรียน",
        )

        response = self.client.post(
            reverse("register"),
            {
                "full_name": "ผู้เรียนใหม่",
                "username": "existinguser",
                "email": "new.learner@example.com",
                "password": "StrongPass123!",
            },
        )

        self.assertRedirects(response, "/#signup-page")
        self.assertFalse(User.objects.filter(email="new.learner@example.com").exists())

    def test_login_accepts_email_and_logout_requires_post(self):
        user = User.objects.create_user(
            username="learner",
            email="learner@example.com",
            password="StrongPass123!",
            full_name="ผู้เรียน",
        )
        response = self.client.post(
            reverse("login"),
            {"identifier": user.email, "password": "StrongPass123!"},
        )

        self.assertRedirects(response, reverse("home"))
        self.assertIn("_auth_user_id", self.client.session)
        self.assertEqual(self.client.get(reverse("logout")).status_code, 405)
        self.assertRedirects(self.client.post(reverse("logout")), reverse("home"))
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_profile_can_update_username_and_upload_profile_image(self):
        user = User.objects.create_user(
            username="learner",
            email="learner@example.com",
            password="StrongPass123!",
            full_name="ผู้เรียน",
        )
        self.client.force_login(user)
        editor_response = self.client.get(reverse("home"))
        self.assertContains(editor_response, 'data-profile-crop-canvas')
        self.assertContains(editor_response, 'data-profile-image-zoom')
        self.assertContains(editor_response, 'data-profile-cropper-status')
        self.assertContains(editor_response, 'accept="image/jpeg,image/png,image/webp"')
        image_file = BytesIO()
        Image.new("RGB", (1, 1), color="blue").save(image_file, format="PNG")
        image = SimpleUploadedFile(
            "profile.png",
            image_file.getvalue(),
            content_type="image/png",
        )

        with tempfile.TemporaryDirectory() as media_root:
            with override_settings(MEDIA_ROOT=media_root):
                response = self.client.post(
                    reverse("edit_profile"),
                    {
                        "username": "my-new-name",
                        "full_name": "ผู้เรียน",
                        "bio": "",
                        "profile_image": image,
                    },
                )

                self.assertRedirects(response, "/#profile-page")
                user.refresh_from_db()
                self.assertEqual(user.username, "my-new-name")
                self.assertTrue(user.profile_image.name.startswith("profiles/"))
                self.assertTrue(user.profile_image.storage.exists(user.profile_image.name))
                self.assertContains(self.client.get(reverse("home")), user.profile_image.url)

    def test_profile_cover_can_be_uploaded_and_previewed(self):
        user = User.objects.create_user(
            username="coverlearner",
            email="coverlearner@example.com",
            password="StrongPass123!",
            full_name="ผู้เรียน",
        )
        self.client.force_login(user)
        image_file = BytesIO()
        Image.new("RGB", (640, 240), color="green").save(image_file, format="PNG")
        image = SimpleUploadedFile(
            "cover.png",
            image_file.getvalue(),
            content_type="image/png",
        )

        with tempfile.TemporaryDirectory() as media_root:
            with override_settings(MEDIA_ROOT=media_root):
                response = self.client.post(
                    reverse("update_profile_cover"),
                    {"profile_cover": image},
                )

                self.assertRedirects(response, "/#profile-page")
                user.refresh_from_db()
                self.assertTrue(user.profile_cover.name.startswith("profile_covers/"))
                self.assertTrue(user.profile_cover.storage.exists(user.profile_cover.name))
                self.assertContains(
                    self.client.get(reverse("home")),
                    user.profile_cover.url,
                )

    def test_profile_actions_and_cover_save_visibility(self):
        user = User.objects.create_user(
            username="profileactions",
            email="profileactions@example.com",
            password="StrongPass123!",
            full_name="ผู้เรียน",
        )
        self.client.force_login(user)

        response = self.client.get(reverse("home"))
        content = response.content.decode()
        actions_start = content.index('class="profile-account-actions"')
        actions_end = content.index("</div>", actions_start)
        account_actions = content[actions_start:actions_end]
        self.assertIn("ออกจากระบบ", account_actions)
        self.assertIn("ลบบัญชี", account_actions)
        self.assertIn("แก้ไขโปรไฟล์", account_actions)
        self.assertIn('id="delete-account-password"', content)
        self.assertIn("ยืนยันการลบบัญชีถาวร", content)
        self.assertContains(response, "▧ แก้ไขภาพปก")
        self.assertContains(response, 'data-profile-cover-save hidden')
        self.assertNotContains(response, "บันทึกรูปปก")

    def test_profile_shows_communities_the_user_has_joined(self):
        user = User.objects.create_user(
            username="communitylearner",
            email="communitylearner@example.com",
            password="StrongPass123!",
            full_name="ผู้เรียน",
        )
        community = Community.objects.create(
            name="ชุมชนคนรักการอ่าน",
            description="แบ่งปันหนังสือและการอ่าน",
            owner=user,
        )
        CommunityMember.objects.create(community=community, user=user)
        self.client.force_login(user)

        response = self.client.get(reverse("home"))

        self.assertContains(response, "Community ที่เราอยู่")
        self.assertContains(response, "ชุมชนคนรักการอ่าน")
        self.assertContains(response, f'href="#community-{community.pk}"')
        self.assertContains(response, "1 แห่ง")

    def test_account_deletion_requires_password_and_transfers_community_owner(self):
        owner = User.objects.create_user(
            username="leavingowner",
            email="owner@example.com",
            password="StrongPass123!",
            full_name="เจ้าของเดิม",
        )
        member = User.objects.create_user(
            username="communitymember",
            email="member@example.com",
            password="StrongPass123!",
            full_name="สมาชิก",
        )
        community = Community.objects.create(
            name="ชุมชนที่ยังใช้งาน",
            description="ชุมชนนี้ต้องอยู่ต่อหลังเจ้าของลบบัญชี",
            owner=owner,
        )
        CommunityMember.objects.create(community=community, user=owner)
        CommunityMember.objects.create(community=community, user=member)
        Post.objects.create(user=owner, community=community, content="โพสต์ที่จะถูกลบ")
        self.client.force_login(owner)

        wrong_password = self.client.post(
            reverse("delete_account"),
            {"password": "incorrect"},
        )
        self.assertRedirects(wrong_password, "/#profile-page")
        self.assertTrue(User.objects.filter(pk=owner.pk).exists())

        response = self.client.post(
            reverse("delete_account"),
            {"password": "StrongPass123!"},
        )

        self.assertRedirects(response, reverse("home"))
        self.assertFalse(User.objects.filter(pk=owner.pk).exists())
        community.refresh_from_db()
        self.assertEqual(community.owner, member)
        self.assertFalse(Post.objects.filter(content="โพสต์ที่จะถูกลบ").exists())
        self.assertNotIn("_auth_user_id", self.client.session)
