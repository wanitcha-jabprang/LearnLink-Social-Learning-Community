from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.shortcuts import get_object_or_404, redirect
from django.utils.text import slugify
from django.views.decorators.http import require_POST

from .forms import UserProfileForm
from .models import Follow, User

def login_view(request):
    if request.method != "POST":
        return redirect("home")

    identifier = request.POST.get("identifier", "").strip()
    password = request.POST.get("password", "")
    username = identifier
    if "@" in identifier:
        user = User.objects.filter(email__iexact=identifier).first()
        username = user.username if user else ""
    user = authenticate(request, username=username, password=password)
    if user is None:
        messages.error(request, "อีเมล/ชื่อผู้ใช้หรือรหัสผ่านไม่ถูกต้อง")
        return redirect("home")
    login(request, user)
    return redirect("home")


def register_view(request):
    if request.method != "POST":
        return redirect("home")

    full_name = request.POST.get("full_name", "").strip()
    email = request.POST.get("email", "").strip()
    password = request.POST.get("password", "")
    if not full_name or not email or not password:
        messages.error(request, "กรุณากรอกชื่อ อีเมล และรหัสผ่านให้ครบ")
        return redirect("/#signup-page")
    try:
        validate_email(email)
    except ValidationError:
        messages.error(request, "กรุณากรอกอีเมลให้ถูกต้อง")
        return redirect("/#signup-page")
    if len(full_name) > 100:
        messages.error(request, "ชื่อต้องมีความยาวไม่เกิน 100 ตัวอักษร")
        return redirect("/#signup-page")
    if User.objects.filter(email__iexact=email).exists():
        messages.error(request, "อีเมลนี้ถูกใช้แล้ว")
        return redirect("/#signup-page")

    username_base = slugify(email.split("@", 1)[0])[:150] or "learner"
    username = username_base
    suffix = 1
    while User.objects.filter(username=username).exists():
        suffix += 1
        suffix_text = str(suffix)
        username = f"{username_base[:150 - len(suffix_text)]}{suffix_text}"

    user = User(username=username, full_name=full_name, email=email)
    try:
        validate_password(password, user)
    except ValidationError as error:
        for message in error.messages:
            messages.error(request, message)
        return redirect("/#signup-page")

    user.set_password(password)
    user.save()
    login(request, user)
    return redirect("home")


def profile_view(request):
    if request.user.is_authenticated:
        return redirect("/#profile-page")
    return redirect("home")


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
            form.save()
            messages.success(request, "บันทึกโปรไฟล์เรียบร้อยแล้ว")
            return redirect("/#profile-page")

        for field_errors in form.errors.values():
            for error in field_errors:
                messages.error(request, error)

    return redirect("/#profile-page")

@login_required
@require_POST
def follow_view(request, user_id):
    target_user = get_object_or_404(User, pk=user_id)

    if target_user == request.user:
        messages.error(request, "ไม่สามารถติดตามตัวเองได้")
        return redirect("home")

    Follow.objects.get_or_create(
        follower=request.user,
        following=target_user,
    )

    messages.success(request, f"ติดตาม {target_user.username} เรียบร้อยแล้ว")
    return redirect("home")


@login_required
@require_POST
def unfollow_view(request, user_id):
    target_user = get_object_or_404(User, pk=user_id)

    Follow.objects.filter(
        follower=request.user,
        following=target_user,
    ).delete()

    messages.success(request, f"เลิกติดตาม {target_user.username} แล้ว")
    return redirect("home")
