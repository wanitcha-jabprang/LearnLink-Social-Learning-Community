from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import redirect
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from community.infrastructure.container import get_community_service


def community_list(request):
    return redirect("/#communities-page")


def community_detail(request, id):
    try:
        community = get_community_service().get(id)
    except LookupError as error:
        raise Http404(str(error)) from error
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
    try:
        community = get_community_service().create(
            name=request.POST.get("name", ""),
            description=request.POST.get("description", "").strip(),
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
    try:
        community = get_community_service().update(
            community_id,
            request.user,
            name=request.POST.get("name", ""),
            description=request.POST.get("description", "").strip(),
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
