import hashlib
from django.contrib import messages
from django.core.cache import cache
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.password_validation import validate_password
from django.db import transaction
from django.core.exceptions import ImproperlyConfigured, ValidationError
from django.core.validators import validate_email
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from community.models import Community, CommunityMember
from post.models import Post
from .forms import ProfileCoverForm, UserProfileForm
from .models import Follow, LoginAttempt, User
from post.models import Post
from django.db.models import Q
from django.utils import timezone
from datetime import timedelta
import pyotp

from .security import encrypt_mfa_secret, decrypt_mfa_secret



def reserve_login_attempt(key):
    now = timezone.now()

    # Create the record if it does not exist.
    # get_or_create() handles concurrent creation using the unique key.
    LoginAttempt.objects.get_or_create(
        key=key,
        defaults={
            "attempts": 0,
            "window_started_at": now,
        },
    )

    # Lock the existing record before updating the counter.
    with transaction.atomic():
        attempt = LoginAttempt.objects.select_for_update().get(
            key=key
        )

        now = timezone.now()

        # Reset the counter after 60 seconds.
        if now - attempt.window_started_at >= timedelta(seconds=60):
            attempt.attempts = 0
            attempt.window_started_at = now

        # Reject requests after 5 attempts.
        if attempt.attempts >= 5:
            return False

        # Reserve one attempt before authentication.
        attempt.attempts += 1
        attempt.save(
            update_fields=["attempts", "window_started_at"]
        )

        return True

    
def login_view(request):
    if request.method != "POST":
        return redirect("home")

    identifier = request.POST.get("identifier", "").strip()
    password = request.POST.get("password", "")

    ip_address = request.META.get("REMOTE_ADDR", "unknown")
    normalized_identifier = identifier.casefold()

    rate_limit_hash = hashlib.sha256(
        f"{ip_address}:{normalized_identifier}".encode("utf-8")
    ).hexdigest()

    if not reserve_login_attempt(rate_limit_hash):
        messages.error(
            request,
            "คุณเข้าสู่ระบบไม่สำเร็จเกินจำนวนครั้งที่กำหนด กรุณาลองใหม่ภายหลัง"
        )
        return redirect("home")

    username = identifier

    if "@" in identifier:
        user = User.objects.filter(email__iexact=identifier).first()
        username = user.username if user else ""

    user = authenticate(request, username=username, password=password)

    if user is None:
        messages.error(
            request,
            "อีเมล/ชื่อผู้ใช้หรือรหัสผ่านไม่ถูกต้อง"
        )
        return redirect("home")

   

    if user.mfa_enabled:
        if not user.mfa_secret_encrypted:
            messages.error(
                request,
                "บัญชีนี้มีปัญหาการตั้งค่า MFA กรุณาติดต่อผู้ดูแลระบบ"
            )
            return redirect("home")

        logout(request)
        request.session["mfa_pending_user_id"] = user.pk
        request.session.set_expiry(300)

        return redirect("verify_mfa")

    login(request, user)
    return redirect("home")



def verify_mfa_view(request):
    pending_user_id = request.session.get("mfa_pending_user_id")

    if not pending_user_id:
        return redirect("home")

    user = User.objects.filter(
        pk=pending_user_id,
        mfa_enabled=True,
    ).first()

    if not user or not user.mfa_secret_encrypted:
        request.session.pop("mfa_pending_user_id", None)
        return redirect("home")

    ip_address = request.META.get("REMOTE_ADDR", "unknown")
    cache_key = f"mfa_failed:{ip_address}:{user.pk}"

    failed_attempts = cache.get(cache_key, 0)

    if failed_attempts >= 5:
        request.session.pop("mfa_pending_user_id", None)
        messages.error(
            request,
            "ยืนยัน OTP ไม่สำเร็จเกินจำนวนครั้งที่กำหนด กรุณาเข้าสู่ระบบใหม่",
        )
        return redirect("home")

    if request.method == "POST":
        otp = request.POST.get("otp", "").strip()

        # ตรวจสอบ Encryption Key และข้อมูล Secret ก่อนตรวจ OTP
        try:
            secret = decrypt_mfa_secret(user.mfa_secret_encrypted)
        except (ValueError, ImproperlyConfigured):
            request.session.pop("mfa_pending_user_id", None)
            messages.error(
                request,
                "ระบบยืนยันตัวตนขัดข้อง กรุณาติดต่อผู้ดูแลระบบ",
            )
            return redirect("home")

        is_valid = (
            len(otp) == 6
            and otp.isdigit()
            and pyotp.TOTP(secret).verify(otp, valid_window=1)
        )

        if not is_valid:
            cache.add(cache_key, 0, timeout=300)
            cache.incr(cache_key)

            failed_attempts = cache.get(cache_key, 0)

            if failed_attempts >= 5:
                request.session.pop("mfa_pending_user_id", None)
                messages.error(
                    request,
                    "ยืนยัน OTP ไม่สำเร็จครบ 5 ครั้ง กรุณาเข้าสู่ระบบใหม่",
                )
                return redirect("home")

            messages.error(request, "รหัส OTP ไม่ถูกต้อง")
            return render(request, "users/verify_mfa.html")

        cache.delete(cache_key)
        request.session.pop("mfa_pending_user_id", None)

        login(request, user)
        return redirect("home")

    return render(request, "users/verify_mfa.html")


def register_view(request):
    if request.method != "POST":
        return redirect("home")

    full_name = request.POST.get("full_name", "").strip()
    username = request.POST.get("username", "").strip()
    email = request.POST.get("email", "").strip()
    password = request.POST.get("password", "")
    if not full_name or not username or not email or not password:
        messages.error(request, "กรุณากรอกชื่อ ชื่อผู้ใช้ อีเมล และรหัสผ่านให้ครบ")
        return redirect("/#signup-page")
    try:
        username = User._meta.get_field("username").clean(username, None)
    except ValidationError as error:
        for message in error.messages:
            messages.error(request, message)
        return redirect("/#signup-page")
    if User.objects.filter(username__iexact=username).exists():
        messages.error(request, "ชื่อผู้ใช้นี้ถูกใช้แล้ว")
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
@login_required
def user_profile_view(request, user_id):

    # ค้นหาผู้ใช้เจ้าของโปรไฟล์
    profile_user = get_object_or_404(User, pk=user_id)

    # ถ้าเป็นโปรไฟล์ตัวเอง ให้กลับไปหน้าโปรไฟล์เดิม
    if profile_user.pk == request.user.pk:
        return redirect("/#profile-page")

    # ดึงโพสต์ที่ผู้เข้าชมมีสิทธิ์ดู
    user_posts = (
        Post.objects.filter(user=profile_user)
        .filter(
            Q(community__isnull=True)
            | Q(community__is_private=False)
            | Q(community__communitymember__user=request.user)
            | Q(community__owner=request.user)
        )
        .select_related("user", "community")
        .prefetch_related("comment_set__user", "like_set")
        .distinct()
        .order_by("-created_at")
    )

    # ตรวจสอบว่าติดตามผู้ใช้นี้อยู่หรือไม่
    is_following = Follow.objects.filter(
        follower=request.user,
        following=profile_user
    ).exists()

    context = {
        "profile_user": profile_user,
        "user_posts": user_posts,
        "is_following": is_following,
        "followers_count": profile_user.followers.count(),
        "following_count": profile_user.following.count(),
        "posts_count": user_posts.count(),
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
            form.save()
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

    user = request.user
    previous_cover = user.profile_cover
    user.profile_cover = form.cleaned_data["profile_cover"]
    user.save(update_fields=["profile_cover"])
    if previous_cover and previous_cover.name != user.profile_cover.name:
        previous_cover.delete(save=False)
    messages.success(request, "เปลี่ยนรูปปกโปรไฟล์เรียบร้อยแล้ว")
    return redirect("/#profile-page")


def delete_stored_files(files_to_delete):
    for storage, name in files_to_delete:
        storage.delete(name)


@login_required
@require_POST
def delete_account_view(request):
    user = request.user
    if not user.check_password(request.POST.get("password", "")):
        messages.error(request, "รหัสผ่านไม่ถูกต้อง จึงยังไม่ได้ลบบัญชี")
        return redirect("/#profile-page")

    files_to_delete = []
    for image_field in (user.profile_image, user.profile_cover):
        if image_field:
            files_to_delete.append((image_field.storage, image_field.name))

    with transaction.atomic():
        owned_communities = Community.objects.filter(owner=user)
        communities_to_delete = []
        for community in owned_communities:
            successor = (
                CommunityMember.objects.filter(community=community)
                .exclude(user=user)
                .select_related("user")
                .order_by("joined_at", "pk")
                .first()
            )
            if successor:
                community.owner = successor.user
                community.save(update_fields=["owner"])
            else:
                communities_to_delete.append(community)
                if community.image:
                    files_to_delete.append(
                        (community.image.storage, community.image.name)
                    )

        posts_to_delete = Post.objects.filter(user=user) | Post.objects.filter(
            community__in=communities_to_delete
        )
        for post in posts_to_delete.distinct().only("image", "video"):
            for media_field in (post.image, post.video):
                if media_field:
                    files_to_delete.append((media_field.storage, media_field.name))

        user.delete()
        transaction.on_commit(lambda: delete_stored_files(files_to_delete))

    logout(request)
    messages.success(request, "ลบบัญชีของคุณเรียบร้อยแล้ว")
    return redirect("home")


@login_required
@require_POST
def follow_view(request, user_id):
    target_user = get_object_or_404(User, pk=user_id)

    # ป้องกันการติดตามตัวเอง
    if target_user.pk == request.user.pk:
        messages.error(request, "ไม่สามารถติดตามตัวเองได้")
        return redirect("profile")

    # ป้องกันการติดตามซ้ำ
    follow, created = Follow.objects.get_or_create(
        follower=request.user,
        following=target_user,
    )

    if created:
        messages.success(
            request,
            f"ติดตาม {target_user.username} เรียบร้อยแล้ว"
        )
    else:
        messages.info(
            request,
            f"คุณกำลังติดตาม {target_user.username} อยู่แล้ว"
        )

    # กลับไปยังหน้าโปรไฟล์เจ้าของโพสต์
    return redirect("user_profile", user_id=target_user.pk)


@login_required
@require_POST
def unfollow_view(request, user_id):
    target_user = get_object_or_404(User, pk=user_id)

    # ป้องกันการเลิกติดตามตัวเอง
    if target_user.pk == request.user.pk:
        messages.error(request, "ไม่สามารถเลิกติดตามตัวเองได้")
        return redirect("profile")

    # ลบความสัมพันธ์การติดตาม
    deleted_count, _ = Follow.objects.filter(
        follower=request.user,
        following=target_user,
    ).delete()

    if deleted_count:
        messages.success(
            request,
            f"เลิกติดตาม {target_user.username} แล้ว"
        )
    else:
        messages.info(
            request,
            f"คุณไม่ได้ติดตาม {target_user.username}"
        )

    # กลับไปยังหน้าโปรไฟล์เดิม
    return redirect("user_profile", user_id=target_user.pk)