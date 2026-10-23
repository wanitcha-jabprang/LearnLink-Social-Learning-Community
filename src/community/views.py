from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from .models import Community, CommunityMember

User = get_user_model()


def community_list(request):
    return redirect("/#communities-page")


def community_detail(request, id):
    community = get_object_or_404(Community, pk=id)
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


@login_required
@require_POST
def create_community(request):
    name = request.POST.get("name", "").strip()
    description = request.POST.get("description", "").strip()
    image = request.FILES.get("image")
    is_private = request.POST.get("is_private") == "true"

    if not name or len(name) > 100:
        messages.error(request, "กรุณากรอกชื่อชุมชนไม่เกิน 100 ตัวอักษร")
        return _redirect_to(request, "/#community-create")

    community = Community.objects.create(
        name=name,
        description=description or "พื้นที่สำหรับแบ่งปันและเรียนรู้ไปด้วยกัน",
        image=image,
        is_private=is_private,
        owner=request.user,
    )
    
    code = community.generate_invite_code()
    CommunityMember.objects.get_or_create(community=community, user=request.user)
    
    if is_private:
        messages.success(request, f"สร้างชุมชนส่วนตัว '{community.name}' เรียบร้อยแล้ว · รหัสเชิญ: {code}")
    else:
        messages.success(request, f"สร้างชุมชนสาธารณะ '{community.name}' เรียบร้อยแล้ว")

    return _redirect_to(request, f"/#community-{community.pk}")


@login_required
@require_POST
def edit_community(request, community_id):
    """เจ้าของชุมชนแก้ไขข้อมูลชุมชน (ชื่อ, รายละเอียด, รูปปก, สถานะส่วนตัว)"""
    community = get_object_or_404(Community, id=community_id)

    if community.owner != request.user:
        messages.error(request, "คุณไม่มีสิทธิ์ในการแก้ไขชุมชนนี้")
        return _redirect_to(request, f"/#community-{community.pk}")

    name = request.POST.get("name", "").strip()
    description = request.POST.get("description", "").strip()
    image = request.FILES.get("image")
    is_private = request.POST.get("is_private") == "true"

    if not name or len(name) > 100:
        messages.error(request, "กรุณากรอกชื่อชุมชนไม่เกิน 100 ตัวอักษร")
        return _redirect_to(request, f"/#community-{community.pk}")

    community.name = name
    community.description = description
    community.is_private = is_private
    
    if image:
        community.image = image
        
    community.save()
    messages.success(request, f"อัปเดตข้อมูลชุมชน '{community.name}' เรียบร้อยแล้ว")
    return _redirect_to(request, f"/#community-{community.pk}")


@login_required
@require_POST
def join_community(request, community_id):
    community = get_object_or_404(Community, pk=community_id)
    if community.is_private and request.POST.get("invite_code", "").strip().upper() != community.invite_code:
        messages.error(request, "รหัสเชิญไม่ถูกต้อง")
        return _redirect_to(request, f"/#community-{community.pk}")
    CommunityMember.objects.get_or_create(community=community, user=request.user)
    messages.success(request, f"เข้าร่วมชุมชน {community.name} แล้ว")
    return _redirect_to(request, f"/#community-{community.pk}")


@login_required
@require_POST
def join_community_by_code(request):
    code = request.POST.get("invite_code", "").strip().upper()
    community = Community.objects.filter(invite_code=code).first()
    if community is None:
        messages.error(request, "ไม่พบชุมชนจากรหัสเชิญนี้")
        return _redirect_to(request)
    CommunityMember.objects.get_or_create(community=community, user=request.user)
    messages.success(request, f"เข้าร่วมชุมชน {community.name} แล้ว")
    return _redirect_to(request, f"/#community-{community.pk}")


@login_required
@require_POST
def leave_community(request, community_id):
    community = get_object_or_404(Community, id=community_id)
    if community.owner_id == request.user.pk:
        messages.error(request, "เจ้าของชุมชนต้องโอนสิทธิ์ความเป็นเจ้าของให้สมาชิกคนอื่นก่อนออกจากชุมชน")
        return _redirect_to(request, f"/#community-{community.pk}")

    CommunityMember.objects.filter(community=community, user=request.user).delete()
    messages.success(request, f"ออกจากชุมชน {community.name} เรียบร้อยแล้ว")
    return _redirect_to(request)


@login_required
@require_POST
def delete_community(request, community_id):
    """เจ้าของชุมชนลบชุมชน"""
    community = get_object_or_404(Community, id=community_id)

    if community.owner != request.user:
        messages.error(request, "คุณไม่มีสิทธิ์ในการลบชุมชนนี้")
        return _redirect_to(request, f"/#community-{community.pk}")

    name = community.name
    community.delete()
    messages.success(request, f"ลบชุมชน {name} เรียบร้อยแล้ว")
    return _redirect_to(request, "/#communities-page")


@login_required
@require_POST
def transfer_ownership(request, community_id):
    """โอนสิทธิ์เจ้าของกลุ่มให้สมาชิกคนอื่น"""
    community = get_object_or_404(Community, id=community_id)
    
    if community.owner != request.user:
        messages.error(request, "คุณไม่มีสิทธิ์โอนความเป็นเจ้าของชุมชนนี้")
        return _redirect_to(request, f"/#community-{community.pk}")

    new_owner_id = request.POST.get("new_owner_id")
    new_owner = get_object_or_404(User, pk=new_owner_id)

    if community.transfer_ownership(new_owner):
        messages.success(request, f"โอนความเป็นเจ้าของให้ {new_owner.username} เรียบร้อยแล้ว")
    else:
        messages.error(request, "ไม่สามารถโอนสิทธิ์ได้ ผู้ใช้คนนี้ไม่ได้เป็นสมาชิกในกลุ่ม")

    return _redirect_to(request, f"/#community-{community.pk}")


@login_required
@require_POST
def remove_member(request, community_id, user_id):
    """เจ้าของกลุ่มลบสมาชิกออกจากกลุ่ม"""
    community = get_object_or_404(Community, id=community_id)

    if community.owner != request.user:
        messages.error(request, "คุณไม่มีสิทธิ์ในการลบสมาชิก")
        return _redirect_to(request, f"/#community-{community.pk}")

    member_to_remove = get_object_or_404(User, pk=user_id)
    if member_to_remove == community.owner:
        messages.error(request, "ไม่สามารถลบเจ้าของชุมชนออกได้")
        return _redirect_to(request, f"/#community-{community.pk}")

    deleted_count, _ = CommunityMember.objects.filter(community=community, user=member_to_remove).delete()
    if deleted_count:
        messages.success(request, f"ลบ {member_to_remove.username} ออกจากชุมชนเรียบร้อยแล้ว")
    else:
        messages.error(request, "ไม่พบสมาชิกคนนี้ในชุมชน")

    return _redirect_to(request, f"/#community-{community.pk}")