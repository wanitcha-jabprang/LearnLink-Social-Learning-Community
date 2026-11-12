
import hashlib
import tempfile
from io import BytesIO
from unittest.mock import patch

import pyotp
from cryptography.fernet import Fernet
from django.contrib import admin
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from PIL import Image

from community.models import Community, CommunityMember
from post.models import Post
from users.models import LoginAttempt, User
from users.security import encrypt_mfa_secret, decrypt_mfa_secret


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
        self.assertFalse(
            User.objects.filter(
                email="new.learner@example.com"
            ).exists()
        )

    def test_login_accepts_email_and_logout_requires_post(self):
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

        self.assertRedirects(response, reverse("home"))
        self.assertIn("_auth_user_id", self.client.session)

        self.assertEqual(
            self.client.get(reverse("logout")).status_code,
            405,
        )

        self.assertRedirects(
            self.client.post(reverse("logout")),
            reverse("home"),
        )
        self.assertNotIn("_auth_user_id", self.client.session)

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

    def test_successful_login_does_not_clear_another_account_counter(self):
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

        self.assertRedirects(response, reverse("home"))
        self.assertIn("_auth_user_id", self.client.session)

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
        cache.clear()

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


class UserAdminSecurityTests(TestCase):

    def setUp(self):
        self.staff_user = User.objects.create_user(
            username="staff_test",
            password="StrongPass123!",
            is_staff=True,
            is_superuser=False,
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

    def test_staff_cannot_edit_privilege_fields(self):
        self.client.force_login(self.staff_user)

        model_admin = admin.site._registry[User]
        readonly_fields = model_admin.get_readonly_fields(
            self.client.request().wsgi_request,
            self.target_user,
        )

        self.assertIn("is_staff", readonly_fields)
        self.assertIn("is_superuser", readonly_fields)

    def test_superuser_can_edit_privilege_fields(self):
        self.client.force_login(self.superuser)

        model_admin = admin.site._registry[User]
        readonly_fields = model_admin.get_readonly_fields(
            self.client.request().wsgi_request,
            self.target_user,
        )

        self.assertNotIn("is_staff", readonly_fields)
        self.assertNotIn("is_superuser", readonly_fields)

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
        self.assertEqual(self.target_user.full_name, "Updated Name")
