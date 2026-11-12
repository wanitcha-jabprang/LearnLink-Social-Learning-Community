from django.test import TransactionTestCase
import tempfile
import uuid
from io import BytesIO
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from PIL import Image

from community.infrastructure.container import get_community_service
from community.infrastructure.persistence.models import (
    Community,
    CommunityDocument,
    CommunityMember,
    CommunityReport,
    PrivateMediaStorage,
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

    # --- Security & Moderation Tests (R-03, R-04, R-07) ---

    def test_community_uses_uuid_primary_key(self):
        community = Community.objects.create(
            name="UUID Community",
            description="",
            invite_code="UUID1234",
            owner=self.owner,
        )
        self.assertIsInstance(community.pk, uuid.UUID)

    def test_private_document_storage_and_access_control(self):
        community = Community.objects.create(
            name="Private Docs Club",
            description="",
            invite_code="DOCS1234",
            is_private=True,
            owner=self.owner,
        )
        CommunityMember.objects.create(community=community, user=self.owner)

        doc_file = SimpleUploadedFile(
            "secret_notes.pdf",
            b"%PDF-1.4 secret content",
            content_type="application/pdf",
        )
        document = CommunityDocument.objects.create(
            community=community,
            uploaded_by=self.owner,
            title="Secret Notes",
            file=doc_file,
        )

        try:
            # 1. Storage ต้องใช้ PrivateMediaStorage และไม่อนุญาตให้เข้าถึงตรงๆ ผ่าน public URL
            self.assertIsInstance(document.file.storage, PrivateMediaStorage)
            with self.assertRaises(ValueError):
                _ = document.file.url

            # 2. คนนอกชุมชน (self.member ที่ยังไม่ join) ต้องดาวน์โหลดไม่ได้
            self.client.force_login(self.member)
            download_url = reverse("download_document", args=[document.pk])
            denied_response = self.client.get(download_url)
            self.assertNotEqual(denied_response.status_code, 200)

            # 3. สมาชิกในชุมชนต้องดาวน์โหลดไฟล์ได้สำเร็จ
            CommunityMember.objects.create(community=community, user=self.member)
            allowed_response = self.client.get(download_url)
            self.assertEqual(allowed_response.status_code, 200)
            self.assertEqual(
                b"".join(allowed_response.streaming_content),
                b"%PDF-1.4 secret content",
            )
        finally:
            if document.file and document.file.storage.exists(document.file.name):
                document.file.storage.delete(document.file.name)

    def test_report_prevents_duplicates_and_cross_community_abuse(self):
        community_a = Community.objects.create(
            name="Community A",
            description="",
            invite_code="COMMA123",
            owner=self.owner,
        )
        community_b = Community.objects.create(
            name="Community B",
            description="",
            invite_code="COMMB123",
            owner=self.owner,
        )
        CommunityMember.objects.create(community=community_a, user=self.member)

        post_in_a = Post.objects.create(
            user=self.owner,
            community=community_a,
            content="โพสต์ในชุมชน A",
        )
        post_in_b = Post.objects.create(
            user=self.owner,
            community=community_b,
            content="โพสต์ในชุมชน B",
        )

        self.client.force_login(self.member)
        report_url_a = reverse("report_item", args=[community_a.pk])

        # 1. รายงานโพสต์ข้ามชุมชน (ส่ง ID ของโพสต์ใน B เข้า endpoint ของ A) ต้องถูกปฏิเสธ
        self.client.post(
            report_url_a,
            {
                "report_type": "POST",
                "target_id": str(post_in_b.pk),
                "reason": "Cross community test",
            },
        )
        self.assertEqual(CommunityReport.objects.count(), 0)

        # 2. ผู้ใช้คนเดิมกดรายงานโพสต์เดิมซ้ำ 3 ครั้ง ต้องบันทึกแค่ 1 ครั้งและไม่ซ่อนโพสต์
        for _ in range(3):
            self.client.post(
                report_url_a,
                {
                    "report_type": "POST",
                    "target_id": str(post_in_a.pk),
                    "reason": "Spam post",
                },
            )

        post_in_a.refresh_from_db()
        self.assertEqual(
            CommunityReport.objects.filter(
                community=community_a,
                target_id=str(post_in_a.pk),
                reporter=self.member,
            ).count(),
            1,
        )
        self.assertFalse(post_in_a.is_hidden)

    def test_post_auto_hides_after_three_distinct_reports_and_disappears_from_feeds(self):
        community = Community.objects.create(
            name="Moderation Club",
            description="",
            invite_code="MOD12345",
            owner=self.owner,
        )
        spam_post = Post.objects.create(
            user=self.owner,
            community=community,
            content="ข้อความสแปมที่ควรถูกซ่อนอัตโนมัติ",
        )

        reporters = [
            User.objects.create_user(
                username=f"reporter{i}",
                email=f"reporter{i}@example.com",
                password="StrongPass123!",
                full_name=f"ผู้รายงาน {i}",
            )
            for i in range(1, 4)
        ]

        report_url = reverse("report_item", args=[community.pk])
        for user in reporters:
            CommunityMember.objects.create(community=community, user=user)
            self.client.force_login(user)
            self.client.post(
                report_url,
                {
                    "report_type": "POST",
                    "target_id": str(spam_post.pk),
                    "reason": "สแปมซ้ำซ้อน",
                },
            )

        # 1. โพสต์ต้องถูกซ่อนอัตโนมัติเมื่อครบ 3 ผู้รายงานที่ไม่ซ้ำกัน
        spam_post.refresh_from_db()
        self.assertTrue(spam_post.is_hidden)

        # 2. โพสต์ต้องหายไปจากหน้าฟีดหลักและหน้าโปรไฟล์ของเจ้าของโพสต์
        self.client.force_login(self.member)
        home_response = self.client.get(reverse("home"))
        self.assertNotContains(home_response, spam_post.content)

        self.client.force_login(self.owner)
        profile_response = self.client.get(reverse("profile"), follow=True)
        self.assertNotContains(profile_response, spam_post.content)

class CommunityReviewRegressionTests(TransactionTestCase):
    def setUp(self):
        from django.contrib.auth import get_user_model
        from community.infrastructure.persistence.models import Community, CommunityMember
        from post.infrastructure.persistence.models import Post

        User = get_user_model()
        self.owner = User.objects.create_user(username="rev_owner", password="password123")
        self.outsider1 = User.objects.create_user(username="outsider1", password="password123")
        self.outsider2 = User.objects.create_user(username="outsider2", password="password123")
        self.outsider3 = User.objects.create_user(username="outsider3", password="password123")

        self.private_comm = Community.objects.create(
            name="Private Study Group",
            description="Members only",
            is_private=True,
            invite_code="PRIV8888",
            owner=self.owner,
        )
        CommunityMember.objects.create(community=self.private_comm, user=self.owner)

        self.post = Post.objects.create(
            user=self.owner,
            community=self.private_comm,
            content="Valid study notes inside private community",
        )

    def test_non_member_cannot_report_post_to_hide_it(self):
        from django.contrib.messages.storage.fallback import FallbackStorage
        from django.test import RequestFactory
        from community.presentation.views import report_item
        from community.infrastructure.persistence.models import CommunityReport

        factory = RequestFactory()

        for outsider in (self.outsider1, self.outsider2, self.outsider3):
            request = factory.post(
                f"/community/{self.private_comm.id}/report/",
                {
                    "report_type": "POST",
                    "target_id": str(self.post.id),
                    "reason": "Malicious external report",
                },
            )
            request.user = outsider
            setattr(request, "session", "session")
            setattr(request, "_messages", FallbackStorage(request))

            response = report_item(request, community_id=self.private_comm.id)
            self.assertEqual(response.status_code, 403)

        self.post.refresh_from_db()
        self.assertFalse(self.post.is_hidden)
        self.assertEqual(CommunityReport.objects.filter(community=self.private_comm).count(), 0)

    def test_migration_0005_migrates_existing_community_members_and_posts(self):
        from django.db.backends.sqlite3.base import DatabaseWrapper
        from django.db.migrations.executor import MigrationExecutor

        from django.db import connection
        cfg = dict(connection.settings_dict)
        cfg["NAME"] = ":memory:"
        from django.db import connections
        test_conn = DatabaseWrapper(cfg, alias="migration_test")
        connections["migration_test"] = test_conn

        try:
            executor = MigrationExecutor(test_conn)
            migrate_from = [("community", "0004_community_image"), ("post", "0003_post_is_hidden")]
            migrate_to = [("community", "0006_alter_communitydocument_file"), ("post", "0005_restore_community_fk")]

            executor.migrate(migrate_from)
            old_apps = executor.loader.project_state(migrate_from).apps

            User = old_apps.get_model("users", "User")
            OldCommunity = old_apps.get_model("community", "Community")
            OldMember = old_apps.get_model("community", "CommunityMember")
            OldPost = old_apps.get_model("post", "Post")

            u1 = User.objects.using(test_conn.alias).create(username="mig_owner", password="pw")
            u2 = User.objects.using(test_conn.alias).create(username="mig_member", password="pw")
            comm = OldCommunity.objects.using(test_conn.alias).create(
                name="Legacy Int Community",
                description="Pre-UUID data",
                is_private=False,
                invite_code="LEGACY01",
                owner=u1,
            )
            OldMember.objects.using(test_conn.alias).create(community=comm, user=u1)
            OldMember.objects.using(test_conn.alias).create(community=comm, user=u2)
            post = OldPost.objects.using(test_conn.alias).create(
                user=u1,
                community=comm,
                content="Legacy post attached to integer community PK",
            )
            old_post_id = post.id

            executor.loader.build_graph()
            executor.migrate(migrate_to)
            new_apps = executor.loader.project_state(migrate_to).apps

            NewCommunity = new_apps.get_model("community", "Community")
            NewMember = new_apps.get_model("community", "CommunityMember")
            NewPost = new_apps.get_model("post", "Post")

            migrated_comm = NewCommunity.objects.using(test_conn.alias).get(name="Legacy Int Community")
            self.assertEqual(NewMember.objects.using(test_conn.alias).filter(community=migrated_comm).count(), 2)
            migrated_post = NewPost.objects.using(test_conn.alias).get(id=old_post_id)
            self.assertEqual(migrated_post.community_id, migrated_comm.id)
        finally:
            test_conn.close()
            del connections["migration_test"]

    def test_rejects_unsupported_report_type(self):
        from django.contrib.messages.storage.fallback import FallbackStorage
        from django.test import RequestFactory
        from community.presentation.views import report_item
        from community.infrastructure.persistence.models import CommunityReport

        factory = RequestFactory()
        request = factory.post(
            f"/community/{self.private_comm.id}/report/",
            {
                "report_type": "UNSUPPORTED_TYPE",
                "target_id": str(self.post.id),
                "reason": "Invalid report type test",
            },
        )
        request.user = self.owner
        setattr(request, "session", "session")
        setattr(request, "_messages", FallbackStorage(request))

        report_item(request, community_id=self.private_comm.id)
        self.assertEqual(CommunityReport.objects.filter(community=self.private_comm).count(), 0)

    def test_user_report_requires_valid_community_member_and_links_reported_user(self):
        from django.contrib.messages.storage.fallback import FallbackStorage
        from django.test import RequestFactory
        from community.presentation.views import report_item
        from community.infrastructure.persistence.models import CommunityMember, CommunityReport

        factory = RequestFactory()

        # 1) รายงาน target_id ที่ไม่มีผู้ใช้จริง -> ต้องไม่สร้างเรคคอร์ด
        req_fake = factory.post(
            f"/community/{self.private_comm.id}/report/",
            {
                "report_type": "USER",
                "target_id": "999999",
                "reason": "Non-existent user",
            },
        )
        req_fake.user = self.owner
        setattr(req_fake, "session", "session")
        setattr(req_fake, "_messages", FallbackStorage(req_fake))
        report_item(req_fake, community_id=self.private_comm.id)
        self.assertEqual(CommunityReport.objects.filter(community=self.private_comm, report_type="USER").count(), 0)

        # 2) รายงานผู้ใช้ที่มีอยู่จริงแต่ไม่ได้อยู่ในชุมชน -> ต้องไม่สร้างเรคคอร์ด
        req_non_member = factory.post(
            f"/community/{self.private_comm.id}/report/",
            {
                "report_type": "USER",
                "target_id": str(self.outsider1.id),
                "reason": "User not in community",
            },
        )
        req_non_member.user = self.owner
        setattr(req_non_member, "session", "session")
        setattr(req_non_member, "_messages", FallbackStorage(req_non_member))
        report_item(req_non_member, community_id=self.private_comm.id)
        self.assertEqual(CommunityReport.objects.filter(community=self.private_comm, report_type="USER").count(), 0)

        # 3) รายงานสมาชิกในชุมชนจริง -> ต้องบันทึกสำเร็จและเชื่อม reported_user ถูกต้อง
        CommunityMember.objects.create(community=self.private_comm, user=self.outsider1)
        req_valid = factory.post(
            f"/community/{self.private_comm.id}/report/",
            {
                "report_type": "USER",
                "target_id": str(self.outsider1.id),
                "reason": "Spamming in community chat",
            },
        )
        req_valid.user = self.owner
        setattr(req_valid, "session", "session")
        setattr(req_valid, "_messages", FallbackStorage(req_valid))
        report_item(req_valid, community_id=self.private_comm.id)

        report = CommunityReport.objects.get(community=self.private_comm, report_type="USER")
        self.assertEqual(report.reported_user_id, self.outsider1.id)
        self.assertEqual(report.target_id, str(self.outsider1.id))
