import os
import re
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import Http404, HttpResponseForbidden, FileResponse
from django.shortcuts import redirect, get_object_or_404
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from community.infrastructure.container import get_community_service
from community.infrastructure.persistence.models import Community, CommunityDocument, CommunityReport

# 🔒 R-07 Spam Filtering Keywords List
FORBIDDEN_KEYWORDS = ["spam", "gambling", "casino", "scam", "พนัน", "คาสิโน"]


def contains_forbidden_keywords(text):
    if not text:
        return False
    pattern = re.compile("|".join(re.escape(word) for word in FORBIDDEN_KEYWORDS), re.IGNORECASE)
    return bool(pattern.search(text))


def community_list(request):
    return redirect("/#communities-page")


# 🔒 R-03 Check Authorization (403 Forbidden for Non-Members in Private Community)
def community_detail(request, id):
    try:
        community = get_community_service().get(id)
    except LookupError as error:
        raise Http404(str(error)) from error

    # 🔒 R-03: ตรวจสอบสิทธิ์ Private Community หากไม่ใช่สมาชิกให้ตอบกลับด้วย 403 Forbidden
    if community.is_private:
        if not request.user.is_authenticated or not community.is_member(request.user):
            return HttpResponseForbidden("403 Forbidden: คุณไม่มีสิทธิ์เข้าถึงชุมชนส่วนตัวนี้")

    return redirect(f"/#community-{community.pk}")


def _redirect_to(request, fallback="/#communities-page"):
    destination = request.POST.get("next", fallback)
    if not url_has_allowed_host_and_scheme(
        destination,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        destination = fallback
    return redirect(destination)


def _handle_service_error(request, error, fallback):
    messages.error(request, str(error))
    return _redirect_to(request, fallback)


@login_required
@require_POST
def create_community(request):
    name = request.POST.get("name", "")
    description = request.POST.get("description", "").strip()

    # 🔒 R-07: Spam Keyword Filter Check
    if contains_forbidden_keywords(name) or contains_forbidden_keywords(description):
        messages.error(request, "เนื้อหามีคำต้องห้ามที่เป็นสแปมหรือการพนัน กรุณาแก้ไขข้อมูล")
        return _redirect_to(request, "/#community-create")

    try:
        community = get_community_service().create(
            name=name,
            description=description,
            image=request.FILES.get("image"),
            is_private=request.POST.get("is_private") == "true",
            owner=request.user,
        )
    except ValueError as error:
        messages.error(request, str(error))
        return _redirect_to(request, "/#community-create")

    if community.is_private:
        messages.success(
            request,
            (
                f"สร้างชุมชนส่วนตัว '{community.name}' เรียบร้อยแล้ว · "
                f"รหัสเชิญ: {community.invite_code}"
            ),
        )
    else:
        messages.success(
            request, f"สร้างชุมชนสาธารณะ '{community.name}' เรียบร้อยแล้ว"
        )
    return _redirect_to(request, f"/#community-{community.pk}")


@login_required
@require_POST
def edit_community(request, community_id):
    name = request.POST.get("name", "")
    description = request.POST.get("description", "").strip()

    # 🔒 R-07: Spam Keyword Filter Check
    if contains_forbidden_keywords(name) or contains_forbidden_keywords(description):
        messages.error(request, "เนื้อหามีคำต้องห้ามที่เป็นสแปมหรือการพนัน กรุณาแก้ไขข้อมูล")
        return _redirect_to(request, f"/#community-{community_id}")

    try:
        community = get_community_service().update(
            community_id,
            request.user,
            name=name,
            description=description,
            image=request.FILES.get("image"),
            is_private=request.POST.get("is_private") == "true",
        )
    except (LookupError, PermissionError, ValueError) as error:
        return _handle_service_error(
            request, error, f"/#community-{community_id}"
        )
    messages.success(request, f"อัปเดตข้อมูลชุมชน '{community.name}' เรียบร้อยแล้ว")
    return _redirect_to(request, f"/#community-{community.pk}")


@login_required
@require_POST
def join_community(request, community_id):
    try:
        community = get_community_service().join(
            community_id,
            request.user,
            request.POST.get("invite_code", ""),
        )
    except (LookupError, ValueError) as error:
        return _handle_service_error(
            request, error, f"/#community-{community_id}"
        )
    messages.success(request, f"เข้าร่วมชุมชน {community.name} แล้ว")
    return _redirect_to(request, f"/#community-{community.pk}")


@login_required
@require_POST
def join_community_by_code(request):
    try:
        community = get_community_service().join_by_code(
            request.POST.get("invite_code", ""),
            request.user,
        )
    except LookupError as error:
        return _handle_service_error(request, error, "/#communities-page")
    messages.success(request, f"เข้าร่วมชุมชน {community.name} แล้ว")
    return _redirect_to(request, f"/#community-{community.pk}")


@login_required
@require_POST
def leave_community(request, community_id):
    try:
        community = get_community_service().leave(community_id, request.user)
    except (LookupError, PermissionError) as error:
        return _handle_service_error(
            request, error, f"/#community-{community_id}"
        )
    messages.success(request, f"ออกจากชุมชน {community.name} เรียบร้อยแล้ว")
    return _redirect_to(request)


@login_required
@require_POST
def delete_community(request, community_id):
    try:
        name = get_community_service().delete(community_id, request.user)
    except (LookupError, PermissionError) as error:
        return _handle_service_error(
            request, error, f"/#community-{community_id}"
        )
    messages.success(request, f"ลบชุมชน {name} เรียบร้อยแล้ว")
    return _redirect_to(request, "/#communities-page")


@login_required
@require_POST
def transfer_ownership(request, community_id):
    try:
        community = get_community_service().transfer_ownership(
            community_id,
            request.user,
            request.POST.get("new_owner_id"),
        )
    except (LookupError, PermissionError, ValueError) as error:
        return _handle_service_error(
            request, error, f"/#community-{community_id}"
        )
    messages.success(
        request,
        f"โอนความเป็นเจ้าของให้ {community.owner.username} เรียบร้อยแล้ว",
    )
    return _redirect_to(request, f"/#community-{community.pk}")


@login_required
@require_POST
def remove_member(request, community_id, user_id):
    try:
        community = get_community_service().remove_member(
            community_id,
            request.user,
            user_id,
        )
    except (LookupError, PermissionError, ValueError) as error:
        return _handle_service_error(
            request, error, f"/#community-{community_id}"
        )
    messages.success(request, "ลบสมาชิกออกจากชุมชนเรียบร้อยแล้ว")
    return _redirect_to(request, f"/#community-{community.pk}")


# 🔒 R-04 Private File Access (เช็กสิทธิ์สมาชิกก่อนให้ดาวน์โหลดไฟล์)
@login_required
def download_document(request, document_id):
    document = get_object_or_404(CommunityDocument, id=document_id)
    community = document.community

    # เช็กว่าผู้ใช้เป็นสมาชิกของชุมชนหรือไม่
    if not community.is_member(request.user):
        return HttpResponseForbidden("403 Forbidden: คุณไม่มีสิทธิ์ดาวน์โหลดไฟล์นี้")

    if not document.file or not os.path.exists(document.file.path):
        raise Http404("ไม่พบไฟล์เอกสาร")

    return FileResponse(open(document.file.path, 'rb'), as_attachment=True, filename=os.path.basename(document.file.name))


# 🔒 R-07 Report System View (รายงาน Post หรือ User)
@login_required
@require_POST
def report_item(request, community_id):
    community = get_object_or_404(Community, id=community_id)
    report_type = request.POST.get("report_type", "POST")
    target_id = request.POST.get("target_id", "")
    reason = request.POST.get("reason", "").strip()

    if not reason or not target_id:
        messages.error(request, "กรุณากรอกข้อมูลการรายงานให้ครบถ้วน")
        return _redirect_to(request, f"/#community-{community_id}")

    CommunityReport.objects.create(
        community=community,
        reporter=request.user,
        report_type=report_type,
        target_id=target_id,
        reason=reason,
    )

    messages.success(request, "ส่งรายงานเรียบร้อยแล้ว ทีมงานจะดำเนินการตรวจสอบโดยเร็ว")
    return _redirect_to(request, f"/#community-{community_id}")