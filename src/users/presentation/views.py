from django.contrib import messages
from django.contrib.auth import authenticate, logout
from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from users.infrastructure.container import get_user_services
from users.presentation.forms import ProfileCoverForm, UserProfileForm


def login_view(request):
    if request.method != "POST":
        return redirect("home")

    identifier = request.POST.get("identifier", "").strip()
    username = get_user_services().accounts.login_username(identifier)
    user = authenticate(
        request,
        username=username,
        password=request.POST.get("password", ""),
    )
    if user is None:
        messages.error(request, "อีเมล/ชื่อผู้ใช้หรือรหัสผ่านไม่ถูกต้อง")
        return redirect("home")
    logout(request)
    if user.mfa_enabled:
        if not user.mfa_secret_encrypted:
            messages.error(
                request,
                "บัญชีนี้มีปัญหาการตั้งค่า MFA กรุณาติดต่อผู้ดูแลระบบ",
            )
            return redirect("home")
        request.session["mfa_pending_user_id"] = user.pk
        request.session.set_expiry(300)
        return redirect("verify_mfa")

    request.session["mfa_enrollment_user_id"] = user.pk
    request.session.set_expiry(600)
    return redirect("setup_mfa")


def register_view(request):
    if request.method != "POST":
        return redirect("home")

    try:
        user = get_user_services().accounts.register(
            full_name=request.POST.get("full_name", ""),
            username=request.POST.get("username", ""),
            email=request.POST.get("email", ""),
            password=request.POST.get("password", ""),
        )
    except ValueError as error:
        for message in str(error).splitlines():
            messages.error(request, message)
        return redirect("/#signup-page")

    logout(request)
    request.session["mfa_enrollment_user_id"] = user.pk
    request.session.set_expiry(600)
    return redirect("setup_mfa")


def profile_view(request):
    if request.user.is_authenticated:
        return redirect("/#profile-page")
    return redirect("home")


@login_required
def user_profile_view(request, user_id):
    services = get_user_services()
    profile_user = services.accounts.get_user(user_id)
    if profile_user is None:
        raise Http404("ไม่พบผู้ใช้นี้")
    if profile_user.pk == request.user.pk:
        return redirect("/#profile-page")

    user_posts = services.profiles.visible_posts(profile_user, request.user)
    context = {
        "profile_user": profile_user,
        "user_posts": user_posts,
        "is_following": services.follows.is_following(
            request.user, profile_user
        ),
        **services.profiles.counts(profile_user, user_posts),
    }
    return render(request, "users/user_profile.html", context)


@require_POST
def logout_view(request):
    logout(request)
    return redirect("home")


@login_required
def edit_profile_view(request):
    if request.method == "POST":
        form = UserProfileForm(
            request.POST,
            request.FILES,
            instance=request.user,
        )
        if form.is_valid():
            user = form.save(commit=False)
            get_user_services().profiles.save(user, form.changed_data)
            messages.success(request, "บันทึกโปรไฟล์เรียบร้อยแล้ว")
            return redirect("/#profile-page")

        for field_errors in form.errors.values():
            for error in field_errors:
                messages.error(request, error)

    return redirect("/#profile-page")


@login_required
@require_POST
def update_profile_cover_view(request):
    form = ProfileCoverForm(request.POST, request.FILES)
    if not form.is_valid():
        for errors in form.errors.values():
            for error in errors:
                messages.error(request, error)
        return redirect("/#profile-page")

    get_user_services().profiles.update_cover(
        request.user,
        form.cleaned_data["profile_cover"],
    )
    messages.success(request, "เปลี่ยนรูปปกโปรไฟล์เรียบร้อยแล้ว")
    return redirect("/#profile-page")


@login_required
@require_POST
def delete_account_view(request):
    services = get_user_services()
    if not services.account_deletion.password_matches(
        request.user,
        request.POST.get("password", ""),
    ):
        messages.error(request, "รหัสผ่านไม่ถูกต้อง จึงยังไม่ได้ลบบัญชี")
        return redirect("/#profile-page")

    services.account_deletion.delete_account(request.user)
    logout(request)
    messages.success(request, "ลบบัญชีของคุณเรียบร้อยแล้ว")
    return redirect("home")


@login_required
@require_POST
def follow_view(request, user_id):
    services = get_user_services()
    target_user = services.accounts.get_user(user_id)
    if target_user is None:
        raise Http404("ไม่พบผู้ใช้นี้")
    try:
        created = services.follows.follow(request.user, target_user)
    except ValueError as error:
        messages.error(request, str(error))
        return redirect("profile")

    if created:
        messages.success(request, f"ติดตาม {target_user.username} เรียบร้อยแล้ว")
    else:
        messages.info(request, f"คุณกำลังติดตาม {target_user.username} อยู่แล้ว")
    return redirect("user_profile", user_id=target_user.pk)


@login_required
@require_POST
def unfollow_view(request, user_id):
    services = get_user_services()
    target_user = services.accounts.get_user(user_id)
    if target_user is None:
        raise Http404("ไม่พบผู้ใช้นี้")
    try:
        deleted = services.follows.unfollow(request.user, target_user)
    except ValueError as error:
        messages.error(request, str(error))
        return redirect("profile")

    if deleted:
        messages.success(request, f"เลิกติดตาม {target_user.username} แล้ว")
    else:
        messages.info(request, f"คุณไม่ได้ติดตาม {target_user.username}")
    return redirect("user_profile", user_id=target_user.pk)
