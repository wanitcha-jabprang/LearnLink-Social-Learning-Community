from django.urls import path

from . import views

urlpatterns = [
    path("", views.community_list, name="community"),
    path("create/", views.create_community, name="create_community"),
    path("join/", views.join_community_by_code, name="join_community_by_code"),
    
    # 🔒 R-03: ปรับชนิดข้อมูลจาก <int:community_id> เป็น <uuid:community_id> เพื่อรองรับ UUID ป้องกัน IDOR
    path(
        "<uuid:community_id>/join/", views.join_community, name="join_community"
    ),
    path(
        "<uuid:community_id>/leave/",
        views.leave_community,
        name="leave_community",
    ),
    path(
        "<uuid:community_id>/edit/", views.edit_community, name="edit_community"
    ),
    path(
        "<uuid:community_id>/delete/",
        views.delete_community,
        name="delete_community",
    ),
    path(
        "<uuid:community_id>/transfer-ownership/",
        views.transfer_ownership,
        name="transfer_ownership",
    ),
    path(
        "<uuid:community_id>/members/<int:user_id>/remove/",
        views.remove_member,
        name="remove_member",
    ),
    path("<uuid:id>/", views.community_detail, name="community_detail"),

    # 🔒 R-04 Private File Access: เส้นทางสำหรับการดาวน์โหลดเอกสารชุมชนอย่างปลอดภัย
    path(
        "documents/<uuid:document_id>/download/",
        views.download_document,
        name="download_document",
    ),

    # 🔒 R-07 Spam Moderation: เส้นทางสำหรับส่งรายงาน (Report Post/User)
    path(
        "<uuid:community_id>/report/",
        views.report_item,
        name="report_item",
    ),
]