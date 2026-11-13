import tempfile
from io import BytesIO
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from PIL import Image

from common.infrastructure.storage.upload_validation import (
    MAX_IMAGE_SIZE,
    validate_image,
)
from community.infrastructure.persistence.models import (
    Community,
    CommunityMember,
)
from post.infrastructure.persistence.models import Post
from users.infrastructure.persistence.models import User
from users.presentation.forms import ProfileCoverForm, UserProfileForm


class AuthenticationFlowTests(TestCase):
    def setUp(self):
        super().setUp()
        scanner = patch(
            "common.infrastructure.storage."
            "upload_validation.scan_uploaded_file",
            return_value=None,
        )
        scanner.start()
        self.addCleanup(scanner.stop)

    def test_registration_starts_required_mfa_enrollment(self):
        response = self.client.post(
            reverse("register"),
            {
                "full_name": "ผู้เรียนใหม่",
                "username": "my-chosen-name",
                "email": "new.learner@example.com",
                "password": "StrongPass123!",
            },
        )

        self.assertRedirects(
            response,
            reverse("setup_mfa"),
            fetch_redirect_response=False,
        )
        user = User.objects.get(email="new.learner@example.com")
        self.assertEqual(user.full_name, "ผู้เรียนใหม่")
        self.assertEqual(user.username, "my-chosen-name")
        self.assertTrue(user.check_password("StrongPass123!"))
        self.assertNotIn("_auth_user_id", self.client.session)
        self.assertEqual(
            self.client.session["mfa_enrollment_user_id"],
            user.pk,
        )

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
        self.assertFalse(
            User.objects.filter(email="new.learner@example.com").exists()
        )

    def test_login_with_email_starts_required_mfa_enrollment(self):
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

        self.assertRedirects(
            response,
            reverse("setup_mfa"),
            fetch_redirect_response=False,
        )
        self.assertNotIn("_auth_user_id", self.client.session)
        self.assertEqual(
            self.client.session["mfa_enrollment_user_id"],
            user.pk,
        )

    def test_profile_can_update_username_and_upload_profile_image(self):
        user = User.objects.create_user(
            username="learner",
            email="learner@example.com",
            password="StrongPass123!",
            full_name="ผู้เรียน",
        )
        self.client.force_login(user)
        editor_response = self.client.get(reverse("home"))
        self.assertContains(editor_response, "data-profile-crop-canvas")
        self.assertContains(editor_response, "data-profile-image-zoom")
        self.assertContains(editor_response, "data-profile-cropper-status")
        self.assertContains(
            editor_response, 'accept="image/jpeg,image/png,image/webp"'
        )
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
                self.assertTrue(
                    user.profile_image.name.startswith("profiles/")
                )
                self.assertTrue(
                    user.profile_image.storage.exists(user.profile_image.name)
                )
                self.assertContains(
                    self.client.get(reverse("home")), user.profile_image.url
                )

    def test_profile_cover_can_be_uploaded_and_previewed(self):
        user = User.objects.create_user(
            username="coverlearner",
            email="coverlearner@example.com",
            password="StrongPass123!",
            full_name="ผู้เรียน",
        )
        self.client.force_login(user)
        image_file = BytesIO()
        Image.new("RGB", (640, 240), color="green").save(
            image_file, format="PNG"
        )
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
                self.assertTrue(
                    user.profile_cover.name.startswith("profile_covers/")
                )
                self.assertTrue(
                    user.profile_cover.storage.exists(user.profile_cover.name)
                )
                self.assertContains(
                    self.client.get(reverse("home")),
                    user.profile_cover.url,
                )

    def test_profile_image_and_cover_validation_runs_on_server(self):
        user = User.objects.create_user(
            username="validateduser",
            email="validated@example.com",
            password="StrongPass123!",
            full_name="ผู้เรียน",
        )
        image_file = BytesIO()
        Image.new("RGB", (1, 1), color="blue").save(image_file, format="PNG")

        with patch(
            "users.presentation.forms.validate_image",
            return_value="รูปภาพต้องมีขนาดไม่เกิน 10 MB",
        ):
            profile_form = UserProfileForm(
                data={
                    "username": user.username,
                    "full_name": user.full_name,
                    "bio": "",
                },
                files={
                    "profile_image": SimpleUploadedFile(
                        "profile.png",
                        image_file.getvalue(),
                        content_type="image/png",
                    )
                },
                instance=user,
            )
            cover_form = ProfileCoverForm(
                files={
                    "profile_cover": SimpleUploadedFile(
                        "cover.png",
                        image_file.getvalue(),
                        content_type="image/png",
                    )
                }
            )
            profile_valid = profile_form.is_valid()
            cover_valid = cover_form.is_valid()

        self.assertFalse(profile_valid)
        self.assertIn("10 MB", str(profile_form.errors["profile_image"]))
        self.assertFalse(cover_valid)
        self.assertIn("10 MB", str(cover_form.errors["profile_cover"]))

    def test_image_validation_rejects_corrupted_file(self):
        image = SimpleUploadedFile(
            "corrupted.png",
            b"not a valid image",
            content_type="image/png",
        )

        self.assertEqual(validate_image(image), "ไฟล์รูปภาพไม่ถูกต้อง")

    def test_image_validation_accepts_valid_upload(self):
        image_file = BytesIO()
        Image.new("RGB", (1, 1), color="blue").save(
            image_file,
            format="PNG",
        )
        image = SimpleUploadedFile(
            "valid.png",
            image_file.getvalue(),
            content_type="image/png",
        )

        self.assertIsNone(validate_image(image))

    def test_image_validation_accepts_only_supported_formats(self):
        for image_format in ("JPEG", "PNG", "WEBP"):
            with self.subTest(image_format=image_format):
                image_file = BytesIO()
                Image.new("RGB", (2, 2), color="blue").save(
                    image_file,
                    format=image_format,
                )
                image = SimpleUploadedFile(
                    f"valid.{image_format.lower()}",
                    image_file.getvalue(),
                    content_type=f"image/{image_format.lower()}",
                )

                self.assertIsNone(validate_image(image))

        image_file = BytesIO()
        Image.new("RGB", (2, 2), color="blue").save(image_file, format="GIF")
        unsupported_image = SimpleUploadedFile(
            "unsupported.gif",
            image_file.getvalue(),
            content_type="image/gif",
        )

        self.assertEqual(
            validate_image(unsupported_image),
            "รองรับเฉพาะไฟล์รูปภาพ JPEG, PNG และ WEBP",
        )

    def test_image_validation_rejects_decompression_bomb_warning(self):
        image_file = BytesIO()
        Image.new("RGB", (10, 10), color="blue").save(
            image_file,
            format="PNG",
        )
        image = SimpleUploadedFile(
            "large-dimensions.png",
            image_file.getvalue(),
            content_type="image/png",
        )

        with patch.object(Image, "MAX_IMAGE_PIXELS", 50):
            error = validate_image(image)

        self.assertEqual(error, "รูปภาพมีขนาดพิกเซลเกินกำหนด")

    def test_shared_image_validation_rejects_oversized_uploads(self):
        class OversizedUpload:
            size = MAX_IMAGE_SIZE + 1

        self.assertEqual(
            validate_image(OversizedUpload()),
            "รูปภาพต้องมีขนาดไม่เกิน 10 MB",
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
        self.assertContains(response, "data-profile-cover-save hidden")
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

    def test_account_deletion_requires_password_and_transfers_community_owner(
        self,
    ):
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
        Post.objects.create(
            user=owner, community=community, content="โพสต์ที่จะถูกลบ"
        )
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


import hashlib
import tempfile
from io import BytesIO
from unittest.mock import patch
from datetime import timedelta
from io import StringIO

from django.core.management import call_command
from django.utils import timezone
import pyotp
from cryptography.fernet import Fernet
from django.contrib import admin
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from PIL import Image

from community.infrastructure.persistence.models import Community, CommunityMember
from post.infrastructure.persistence.models import Post
from users.infrastructure.persistence.models import LoginAttempt, User
from users.security import encrypt_mfa_secret, decrypt_mfa_secret
from django.contrib.auth.models import Permission
from django.test import RequestFactory

class LegacyAuthenticationFlowTests(TestCase):
    def setUp(self):
        super().setUp()
        scanner = patch(
            "common.infrastructure.storage."
            "upload_validation.scan_uploaded_file",
            return_value=None,
        )
        scanner.start()
        self.addCleanup(scanner.stop)

    def test_registration_starts_required_mfa_enrollment(self):
        response = self.client.post(
            reverse("register"),
            {
                "full_name": "ผู้เรียนใหม่",
                "username": "my-chosen-name",
                "email": "new.learner@example.com",
                "password": "StrongPass123!",
            },
        )

        self.assertRedirects(
            response,
            reverse("setup_mfa"),
            fetch_redirect_response=False,
        )
        user = User.objects.get(email="new.learner@example.com")
        self.assertEqual(user.full_name, "ผู้เรียนใหม่")
        self.assertEqual(user.username, "my-chosen-name")
        self.assertTrue(user.check_password("StrongPass123!"))
        self.assertNotIn("_auth_user_id", self.client.session)
        self.assertEqual(
            self.client.session["mfa_enrollment_user_id"],
            user.pk,
        )

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
        self.assertFalse(
            User.objects.filter(
                email="new.learner@example.com"
            ).exists()
        )

    def test_login_with_email_starts_required_mfa_enrollment(self):
        user = User.objects.create_user(
            username="learner",
            email="learner@example.com",
            password="StrongPass123!",
            full_name="ผู้เรียน",
        )

        response = self.client.post(
            reverse("login"),
            {
                "identifier": user.email,
                "password": "StrongPass123!",
            },
        )

        self.assertRedirects(
            response,
            reverse("setup_mfa"),
            fetch_redirect_response=False,
        )
        self.assertNotIn("_auth_user_id", self.client.session)
        self.assertEqual(
            self.client.session["mfa_enrollment_user_id"],
            user.pk,
        )

    def test_login_blocks_after_five_failed_attempts(self):
        login_data = {
            "identifier": "unknown-user",
            "password": "wrong-password",
        }

        for _ in range(5):
            response = self.client.post(
                reverse("login"),
                login_data,
            )
            self.assertRedirects(response, reverse("home"))

        identifier_hash = hashlib.sha256(
            f"127.0.0.1:{login_data['identifier'].casefold()}".encode(
                "utf-8"
            )
        ).hexdigest()

        attempt = LoginAttempt.objects.get(key=identifier_hash)
        self.assertEqual(attempt.attempts, 5)

        with patch("users.views.authenticate") as mock_authenticate:
            response = self.client.post(
                reverse("login"),
                login_data,
            )

        self.assertRedirects(response, reverse("home"))
        mock_authenticate.assert_not_called()

        attempt.refresh_from_db()
        self.assertEqual(attempt.attempts, 5)

    def test_successful_login_starts_mfa_without_clearing_other_counter(self):
        user = User.objects.create_user(
            username="account-two",
            email="account-two@example.com",
            password="StrongPass123!",
            full_name="ผู้เรียน",
        )

        other_identifier = "account-one"

        response = self.client.post(
            reverse("login"),
            {
                "identifier": other_identifier,
                "password": "wrong-password",
            },
        )
        self.assertRedirects(response, reverse("home"))

        other_hash = hashlib.sha256(
            f"127.0.0.1:{other_identifier.casefold()}".encode(
                "utf-8"
            )
        ).hexdigest()

        self.assertEqual(
            LoginAttempt.objects.get(key=other_hash).attempts,
            1,
        )

        response = self.client.post(
            reverse("login"),
            {
                "identifier": user.username,
                "password": "StrongPass123!",
            },
        )

        self.assertRedirects(
            response,
            reverse("setup_mfa"),
            fetch_redirect_response=False,
        )

        self.assertNotIn("_auth_user_id", self.client.session)
        self.assertEqual(
            self.client.session["mfa_enrollment_user_id"],
            user.pk,
        )

        self.assertTrue(
            LoginAttempt.objects.filter(
                key=other_hash,
                attempts=1,
            ).exists()
        )

    def test_login_failed_attempts_are_separated_by_identifier(self):
        identifiers = ["account-one", "account-two"]

        for identifier in identifiers:
            for _ in range(2):
                response = self.client.post(
                    reverse("login"),
                    {
                        "identifier": identifier,
                        "password": "wrong-password",
                    },
                )
                self.assertRedirects(response, reverse("home"))

        for identifier in identifiers:
            identifier_hash = hashlib.sha256(
                f"127.0.0.1:{identifier.casefold()}".encode(
                    "utf-8"
                )
            ).hexdigest()

            attempt = LoginAttempt.objects.get(key=identifier_hash)
            self.assertEqual(attempt.attempts, 2)

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
        self.assertContains(
            editor_response,
            'accept="image/jpeg,image/png,image/webp"',
        )

        image_file = BytesIO()
        Image.new("RGB", (1, 1), color="blue").save(
            image_file,
            format="PNG",
        )

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
                self.assertTrue(
                    user.profile_image.name.startswith("profiles/")
                )
                self.assertTrue(
                    user.profile_image.storage.exists(
                        user.profile_image.name
                    )
                )

                self.assertContains(
                    self.client.get(reverse("home")),
                    user.profile_image.url,
                )

    def test_profile_cover_can_be_uploaded_and_previewed(self):
        user = User.objects.create_user(
            username="coverlearner",
            email="coverlearner@example.com",
            password="StrongPass123!",
            full_name="ผู้เรียน",
        )

        self.client.force_login(user)

        image_file = BytesIO()
        Image.new("RGB", (640, 240), color="green").save(
            image_file,
            format="PNG",
        )

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
                self.assertTrue(
                    user.profile_cover.name.startswith("profile_covers/")
                )
                self.assertTrue(
                    user.profile_cover.storage.exists(
                        user.profile_cover.name
                    )
                )

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

        actions_start = content.index(
            'class="profile-account-actions"'
        )
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

        CommunityMember.objects.create(
            community=community,
            user=user,
        )

        self.client.force_login(user)

        response = self.client.get(reverse("home"))

        self.assertContains(response, "Community ที่เราอยู่")
        self.assertContains(response, "ชุมชนคนรักการอ่าน")
        self.assertContains(
            response,
            f'href="#community-{community.pk}"',
        )
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

        CommunityMember.objects.create(
            community=community,
            user=owner,
        )
        CommunityMember.objects.create(
            community=community,
            user=member,
        )

        Post.objects.create(
            user=owner,
            community=community,
            content="โพสต์ที่จะถูกลบ",
        )

        self.client.force_login(owner)

        wrong_password = self.client.post(
            reverse("delete_account"),
            {"password": "incorrect"},
        )

        self.assertRedirects(wrong_password, "/#profile-page")
        self.assertTrue(
            User.objects.filter(pk=owner.pk).exists()
        )

        response = self.client.post(
            reverse("delete_account"),
            {"password": "StrongPass123!"},
        )

        self.assertRedirects(response, reverse("home"))
        self.assertFalse(
            User.objects.filter(pk=owner.pk).exists()
        )

        community.refresh_from_db()
        self.assertEqual(community.owner, member)

        self.assertFalse(
            Post.objects.filter(
                content="โพสต์ที่จะถูกลบ"
            ).exists()
        )
        self.assertNotIn("_auth_user_id", self.client.session)


class MFAEncryptionTests(TestCase):
    def setUp(self):
        self.key_patcher = patch.dict(
            "os.environ",
            {"MFA_ENCRYPTION_KEY": Fernet.generate_key().decode("utf-8")},
        )
        self.key_patcher.start()
        self.addCleanup(self.key_patcher.stop)

    def test_mfa_secret_can_be_encrypted_and_decrypted(self):
        secret = "JBSWY3DPEHPK3PXP"

        encrypted = encrypt_mfa_secret(secret)
        decrypted = decrypt_mfa_secret(encrypted)

        self.assertNotEqual(encrypted, secret)
        self.assertEqual(decrypted, secret)

    def test_encrypt_rejects_empty_secret(self):
        with self.assertRaises(ValueError):
            encrypt_mfa_secret("")

    def test_decrypt_rejects_empty_encrypted_secret(self):
        with self.assertRaises(ValueError):
            decrypt_mfa_secret("")

    def test_decrypt_rejects_invalid_encrypted_secret(self):
        with self.assertRaises(ValueError):
            decrypt_mfa_secret("invalid-encrypted-value")

    def test_mfa_encryption_requires_encryption_key(self):
        with patch.dict("os.environ", {"MFA_ENCRYPTION_KEY": ""}):
            with self.assertRaises(Exception):
                encrypt_mfa_secret("JBSWY3DPEHPK3PXP")


class MFAVerificationTests(TestCase):
    def setUp(self):
        self.encryption_key = Fernet.generate_key().decode("utf-8")
        self.secret = "JBSWY3DPEHPK3PXP"

        with patch.dict(
            "os.environ",
            {"MFA_ENCRYPTION_KEY": self.encryption_key},
        ):
            encrypted_secret = encrypt_mfa_secret(self.secret)

        self.user = User.objects.create_user(
            username="mfa_user",
            email="mfa@example.com",
            password="StrongPass123!",
            full_name="MFA User",
            mfa_enabled=True,
            mfa_secret_encrypted=encrypted_secret,
        )


    def set_pending_session(self):
        session = self.client.session
        session["mfa_pending_user_id"] = self.user.pk
        session.save()

    def test_verify_mfa_redirects_without_pending_session(self):
        response = self.client.get(reverse("verify_mfa"))

        self.assertRedirects(response, reverse("home"))
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_valid_otp_logs_in_user(self):
        self.set_pending_session()
        otp = pyotp.TOTP(self.secret).now()

        with patch.dict(
            "os.environ",
            {"MFA_ENCRYPTION_KEY": self.encryption_key},
        ):
            response = self.client.post(
                reverse("verify_mfa"),
                {"otp": otp},
            )

        self.assertRedirects(response, reverse("home"))
        self.assertEqual(
            str(self.user.pk),
            self.client.session.get("_auth_user_id"),
        )
        self.assertNotIn(
            "mfa_pending_user_id",
            self.client.session,
        )

    def test_login_requires_otp_before_authenticating_mfa_user(self):
        response = self.client.post(
            reverse("login"),
            {
                "identifier": self.user.email,
                "password": "StrongPass123!",
            },
        )

        self.assertRedirects(response, reverse("verify_mfa"))
        self.assertNotIn("_auth_user_id", self.client.session)
        self.assertEqual(
            self.client.session["mfa_pending_user_id"],
            self.user.pk,
        )

        otp = pyotp.TOTP(self.secret).now()
        with patch.dict(
            "os.environ",
            {"MFA_ENCRYPTION_KEY": self.encryption_key},
        ):
            response = self.client.post(
                reverse("verify_mfa"),
                {"otp": otp},
            )

        self.assertRedirects(response, reverse("home"))
        self.assertEqual(
            self.client.session["_auth_user_id"],
            str(self.user.pk),
        )

    def test_replayed_otp_is_rejected(self):
        self.set_pending_session()
        otp = pyotp.TOTP(self.secret).now()

        with patch.dict(
            "os.environ",
            {"MFA_ENCRYPTION_KEY": self.encryption_key},
        ):
            first_response = self.client.post(
                reverse("verify_mfa"),
                {"otp": otp},
            )

            self.assertRedirects(first_response, reverse("home"))

            # Start a new MFA verification session for the same user.
            self.client.logout()
            self.set_pending_session()

            second_response = self.client.post(
                reverse("verify_mfa"),
                {"otp": otp},
            )

        self.assertEqual(second_response.status_code, 200)
        self.assertNotIn("_auth_user_id", self.client.session)
        self.assertIn(
            "mfa_pending_user_id",
            self.client.session,
        )

        self.user.refresh_from_db()
        self.assertIsNotNone(self.user.mfa_last_used_step)

    def test_new_time_step_otp_is_accepted(self):
        self.set_pending_session()

        totp = pyotp.TOTP(self.secret)
        current_step = totp.timecode(timezone.now())
        next_otp = totp.at((current_step + 1) * totp.interval)

        with (
            patch.dict(
                "os.environ",
                {"MFA_ENCRYPTION_KEY": self.encryption_key},
            ),
            patch(
                "users.views.timezone.now",
                return_value=timezone.now() + timedelta(
                    seconds=totp.interval
                ),
            ),
        ):
            response = self.client.post(
                reverse("verify_mfa"),
                {"otp": next_otp},
            )

        self.assertRedirects(response, reverse("home"))
        self.assertEqual(
            str(self.user.pk),
            self.client.session.get("_auth_user_id"),
        )

        self.user.refresh_from_db()
        self.assertEqual(
            self.user.mfa_last_used_step,
            current_step + 1,
        )

    def test_invalid_otp_is_rejected(self):
        self.set_pending_session()

        with patch.dict(
            "os.environ",
            {"MFA_ENCRYPTION_KEY": self.encryption_key},
        ):
            response = self.client.post(
                reverse("verify_mfa"),
                {"otp": "000000"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertNotIn("_auth_user_id", self.client.session)
        self.assertIn(
            "mfa_pending_user_id",
            self.client.session,
        )

    def test_fifth_invalid_otp_clears_pending_session(self):
        self.set_pending_session()

        with patch.dict(
            "os.environ",
            {"MFA_ENCRYPTION_KEY": self.encryption_key},
        ):
            for _ in range(5):
                response = self.client.post(
                    reverse("verify_mfa"),
                    {"otp": "000000"},
                )

        self.assertRedirects(response, reverse("home"))
        self.assertNotIn(
            "mfa_pending_user_id",
            self.client.session,
        )
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_missing_encryption_key_clears_pending_session(self):
        self.set_pending_session()

        with patch.dict(
            "os.environ",
            {"MFA_ENCRYPTION_KEY": ""},
        ):
            response = self.client.post(
                reverse("verify_mfa"),
                {"otp": "000000"},
            )

        self.assertRedirects(response, reverse("home"))
        self.assertNotIn(
            "mfa_pending_user_id",
            self.client.session,
        )
        self.assertNotIn("_auth_user_id", self.client.session)

class MFAEnrollmentTests(TestCase):
    def setUp(self):
        self.encryption_key = Fernet.generate_key().decode("utf-8")

        self.user = User.objects.create_user(
            username="mfa_enrollment_user",
            email="enrollment@example.com",
            password="StrongPass123!",
            full_name="MFA Enrollment User",
            mfa_enabled=False,
            mfa_secret_encrypted="",
        )

        self.client.force_login(self.user)

    def test_enrollment_page_generates_qr_without_enabling_mfa(self):
        with patch.dict(
            "os.environ",
            {"MFA_ENCRYPTION_KEY": self.encryption_key},
        ):
            response = self.client.get(reverse("setup_mfa"))

        self.assertEqual(response.status_code, 200)
        self.assertIn("data:image/png;base64,", response.context["qr_code_data_uri"])
        self.assertTrue(response.context["secret"])

        self.user.refresh_from_db()
        self.assertFalse(self.user.mfa_enabled)
        self.assertEqual(self.user.mfa_secret_encrypted, "")

        self.assertIn(
            "mfa_enrollment_secret",
            self.client.session,
        )

    def test_invalid_otp_does_not_enable_mfa(self):
        with patch.dict(
            "os.environ",
            {"MFA_ENCRYPTION_KEY": self.encryption_key},
        ):
            self.client.get(reverse("setup_mfa"))

            secret = decrypt_mfa_secret(
                self.client.session["mfa_enrollment_secret"]
            )

            current_otp = pyotp.TOTP(secret).now()
            wrong_otp = str((int(current_otp[0]) + 1) % 10) + current_otp[1:]

            response = self.client.post(
                reverse("setup_mfa"),
                {"otp": wrong_otp},
            )

        self.assertEqual(response.status_code, 200)

        self.user.refresh_from_db()
        self.assertFalse(self.user.mfa_enabled)
        self.assertEqual(self.user.mfa_secret_encrypted, "")

    def test_valid_otp_enables_mfa(self):
        with patch.dict(
            "os.environ",
            {"MFA_ENCRYPTION_KEY": self.encryption_key},
        ):
            self.client.get(reverse("setup_mfa"))

            secret = decrypt_mfa_secret(
                self.client.session["mfa_enrollment_secret"]
            )

            otp = pyotp.TOTP(secret).now()

            response = self.client.post(
                reverse("setup_mfa"),
                {"otp": otp},
            )

            self.user.refresh_from_db()

            self.assertRedirects(response, reverse("home"))
            self.assertTrue(self.user.mfa_enabled)
            self.assertEqual(
                decrypt_mfa_secret(self.user.mfa_secret_encrypted),
                secret,
            )

        self.assertNotIn(
            "mfa_enrollment_secret",
            self.client.session,
        )
        self.assertNotIn(
            "mfa_enrollment_started_at",
            self.client.session,
        )

    def test_registration_completes_mfa_before_authenticating(self):
        with patch.dict(
            "os.environ",
            {"MFA_ENCRYPTION_KEY": self.encryption_key},
        ):
            response = self.client.post(
                reverse("register"),
                {
                    "full_name": "ผู้สมัครใหม่",
                    "username": "new_mfa_user",
                    "email": "new.mfa@example.com",
                    "password": "StrongPass123!",
                },
            )

            self.assertRedirects(response, reverse("setup_mfa"))
            user = User.objects.get(username="new_mfa_user")
            self.assertNotIn("_auth_user_id", self.client.session)

            setup_response = self.client.get(reverse("setup_mfa"))
            self.assertEqual(setup_response.status_code, 200)

            secret = decrypt_mfa_secret(
                self.client.session["mfa_enrollment_secret"]
            )
            response = self.client.post(
                reverse("setup_mfa"),
                {"otp": pyotp.TOTP(secret).now()},
            )

        self.assertRedirects(response, reverse("home"))
        user.refresh_from_db()
        self.assertTrue(user.mfa_enabled)
        self.assertEqual(
            self.client.session["_auth_user_id"],
            str(user.pk),
        )

    def test_enrollment_requires_login(self):
        self.client.logout()

        response = self.client.get(reverse("setup_mfa"))

        self.assertRedirects(response, reverse("home"))

    def test_already_enabled_user_cannot_start_enrollment(self):
        with patch.dict(
            "os.environ",
            {"MFA_ENCRYPTION_KEY": self.encryption_key},
        ):
            original_secret = encrypt_mfa_secret("JBSWY3DPEHPK3PXP")

        self.user.mfa_enabled = True
        self.user.mfa_secret_encrypted = original_secret
        self.user.save()

        response = self.client.get(reverse("setup_mfa"))

        self.assertRedirects(response, reverse("home"))

        self.user.refresh_from_db()
        self.assertTrue(self.user.mfa_enabled)
        self.assertEqual(
            self.user.mfa_secret_encrypted,
            original_secret,
        )

class UserAdminSecurityTests(TestCase):

    def setUp(self):
        self.staff_user = User.objects.create_user(
            username="staff_test",
            password="StrongPass123!",
            is_staff=True,
            is_superuser=False,
        )

        change_user_permission = Permission.objects.get(
            content_type__app_label="users",
            codename="change_user",
        )
        self.staff_user.user_permissions.add(
            change_user_permission
        )

        self.superuser = User.objects.create_superuser(
            username="admin_test",
            password="StrongPass123!",
            email="admin@example.com",
        )

        self.target_user = User.objects.create_user(
            username="target_test",
            password="StrongPass123!",
        )

        self.factory = RequestFactory()

    def test_staff_cannot_edit_privilege_fields(self):
        request = self.factory.get("/admin/")
        request.user = self.staff_user

        model_admin = admin.site._registry[User]
        readonly_fields = model_admin.get_readonly_fields(
            request,
            self.target_user,
        )

        self.assertIn("is_staff", readonly_fields)
        self.assertIn("is_superuser", readonly_fields)

    def test_superuser_can_edit_privilege_fields(self):
        request = self.factory.get("/admin/")
        request.user = self.superuser

        model_admin = admin.site._registry[User]
        readonly_fields = model_admin.get_readonly_fields(
            request,
            self.target_user,
        )

        self.assertNotIn("is_staff", readonly_fields)
        self.assertNotIn("is_superuser", readonly_fields)

    def test_staff_cannot_see_groups_and_user_permissions(self):
        request = self.factory.get("/admin/")
        request.user = self.staff_user

        model_admin = admin.site._registry[User]
        form_class = model_admin.get_form(
            request,
            self.target_user,
        )

        self.assertNotIn("groups", form_class.base_fields)
        self.assertNotIn(
            "user_permissions",
            form_class.base_fields,
        )

    def test_staff_cannot_submit_groups_and_user_permissions(self):
        request = self.factory.post("/admin/")
        request.user = self.staff_user

        model_admin = admin.site._registry[User]
        form_class = model_admin.get_form(
            request,
            self.target_user,
        )

        form = form_class(
            data={
                "username": self.target_user.username,
                "groups": [],
                "user_permissions": [],
            },
            instance=self.target_user,
        )

        self.assertNotIn("groups", form.fields)
        self.assertNotIn("user_permissions", form.fields)

    def test_superuser_can_see_groups_and_user_permissions(self):
        request = self.factory.get("/admin/")
        request.user = self.superuser

        model_admin = admin.site._registry[User]
        form_class = model_admin.get_form(
            request,
            self.target_user,
        )

        self.assertIn("groups", form_class.base_fields)
        self.assertIn(
            "user_permissions",
            form_class.base_fields,
        )

    def test_profile_edit_cannot_change_privilege_fields(self):
        self.client.force_login(self.target_user)

        response = self.client.post(
            reverse("edit_profile"),
            {
                "username": self.target_user.username,
                "full_name": "Updated Name",
                "bio": "Updated bio",
                "is_staff": "True",
                "is_superuser": "True",
            },
        )

        self.assertRedirects(
            response,
            "/#profile-page",
            fetch_redirect_response=False,
        )

        self.target_user.refresh_from_db()
        self.assertFalse(self.target_user.is_staff)
        self.assertFalse(self.target_user.is_superuser)
        self.assertEqual(
            self.target_user.full_name,
            "Updated Name",
        )

class LoginAttemptCleanupTests(TestCase):

    def setUp(self):
        now = timezone.now()

        self.old_attempt = LoginAttempt.objects.create(
            key="old-login-attempt",
            attempts=5,
            window_started_at=now - timedelta(days=31),
        )

        self.recent_attempt = LoginAttempt.objects.create(
            key="recent-login-attempt",
            attempts=2,
            window_started_at=now - timedelta(days=1),
        )

    def test_cleanup_deletes_old_login_attempts(self):
        output = StringIO()

        call_command(
            "cleanup_login_attempts",
            stdout=output,
        )

        self.assertFalse(
            LoginAttempt.objects.filter(
                pk=self.old_attempt.pk
            ).exists()
        )

        self.assertTrue(
            LoginAttempt.objects.filter(
                pk=self.recent_attempt.pk
            ).exists()
        )

    def test_cleanup_supports_custom_days(self):
        output = StringIO()

        call_command(
            "cleanup_login_attempts",
            days=7,
            stdout=output,
        )

        self.assertFalse(
            LoginAttempt.objects.filter(
                pk=self.old_attempt.pk
            ).exists()
        )

        self.assertTrue(
            LoginAttempt.objects.filter(
                pk=self.recent_attempt.pk
            ).exists()
        )

    def test_cleanup_rejects_invalid_days(self):
        output = StringIO()

        call_command(
            "cleanup_login_attempts",
            days=0,
            stdout=output,
        )

        self.assertTrue(
            LoginAttempt.objects.filter(
                pk=self.old_attempt.pk
            ).exists()
        )

        self.assertTrue(
            LoginAttempt.objects.filter(
                pk=self.recent_attempt.pk
            ).exists()
        )
