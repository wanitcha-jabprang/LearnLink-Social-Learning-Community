import hashlib
import base64
from io import BytesIO
import qrcode
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

from redis.exceptions import RedisError
from django.core.cache import cache
import hmac

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


def get_mfa_redis_client():
    """
    Return the Redis client configured by Django.
    """
    return cache._cache.get_client(write=True)


def get_mfa_attempts(key):
    """
    Read the MFA attempt counter from the same Redis key.
    """
    redis_client = get_mfa_redis_client()
    value = redis_client.get(key)

    if value is None:
        return 0

    return int(value)


def reserve_mfa_attempt(key):
    """
    Atomically reserve an OTP attempt.
    Maximum 5 attempts within 300 seconds.
    """
    redis_client = get_mfa_redis_client()

    reserve_script = redis_client.register_script(
        """
        local current = tonumber(redis.call('GET', KEYS[1]) or '0')

        if current >= tonumber(ARGV[1]) then
            return 0
        end

        local count = redis.call('INCR', KEYS[1])

        if count == 1 then
            redis.call('EXPIRE', KEYS[1], tonumber(ARGV[2]))
        end

        return count
        """
    )

    result = reserve_script(
        keys=[key],
        args=[5, 300],
        client=redis_client,
    )

    return bool(result)


def release_mfa_attempt(key):
    """
    Release one reserved OTP attempt.
    """
    redis_client = get_mfa_redis_client()

    release_script = redis_client.register_script(
        """
        local current = tonumber(redis.call('GET', KEYS[1]) or '0')

        if current <= 1 then
            return redis.call('DEL', KEYS[1])
        end

        return redis.call('DECR', KEYS[1])
        """
    )

    release_script(
        keys=[key],
        client=redis_client,
    )


    
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

@login_required(login_url="login")
def mfa_setup_view(request):
    if request.user.mfa_enabled:
        messages.info(request, "บัญชีนี้เปิดใช้งาน MFA อยู่แล้ว")
        return redirect("home")

    secret_key = "mfa_enrollment_secret"
    started_key = "mfa_enrollment_started_at"

    started_at = request.session.get(started_key)
    encrypted_secret = request.session.get(secret_key)

    # Enrollment session expires after 10 minutes.
    if (
        not started_at
        or timezone.now().timestamp() - started_at > 600
        or not encrypted_secret
    ):
        request.session.pop(secret_key, None)
        request.session.pop(started_key, None)

        try:
            secret = pyotp.random_base32()
            encrypted_secret = encrypt_mfa_secret(secret)
        except (ImproperlyConfigured, ValueError):
            messages.error(request, "ไม่สามารถเริ่มตั้งค่า MFA ได้ กรุณาติดต่อผู้ดูแลระบบ")
            return redirect("home")

        request.session[secret_key] = encrypted_secret
        request.session[started_key] = timezone.now().timestamp()

    try:
        secret = decrypt_mfa_secret(encrypted_secret)
    except (ValueError, ImproperlyConfigured):
        request.session.pop(secret_key, None)
        request.session.pop(started_key, None)
        messages.error(request, "ข้อมูลตั้งค่า MFA ไม่ถูกต้อง กรุณาเริ่มใหม่")
        return redirect("home")

    ip_address = request.META.get("REMOTE_ADDR", "unknown")
    cache_key = f"mfa_enroll_failed:{ip_address}:{request.user.pk}"

    if request.method == "POST":
        try:
            reserved = reserve_mfa_attempt(cache_key)
        except Exception:
            messages.error(request, "ระบบยืนยันตัวตนขัดข้อง กรุณาลองใหม่ภายหลัง")
            return redirect("setup_mfa")

        if not reserved:
            messages.error(request, "ยืนยัน OTP เกินจำนวนครั้งที่กำหนด กรุณาลองใหม่ภายหลัง")
            return redirect("setup_mfa")

        otp = request.POST.get("otp", "").strip()
        is_valid = (
            len(otp) == 6
            and otp.isdigit()
            and pyotp.TOTP(secret).verify(otp, valid_window=1)
        )

        if not is_valid:
            messages.error(request, "รหัส OTP ไม่ถูกต้อง")
        else:
            try:
                release_mfa_attempt(cache_key)

                with transaction.atomic():
                    user = User.objects.select_for_update().get(
                        pk=request.user.pk
                    )

                    if user.mfa_enabled:
                        messages.info(request, "บัญชีนี้เปิดใช้งาน MFA อยู่แล้ว")
                    else:
                        user.mfa_secret_encrypted = encrypted_secret
                        user.mfa_enabled = True
                        user.save(
                            update_fields=[
                                "mfa_secret_encrypted",
                                "mfa_enabled",
                            ]
                        )
                        messages.success(request, "เปิดใช้งาน MFA สำเร็จแล้ว")

                request.session.pop(secret_key, None)
                request.session.pop(started_key, None)
                return redirect("home")

            except Exception:
                messages.error(
                    request,
                    "ไม่สามารถบันทึกการตั้งค่า MFA ได้ กรุณาลองใหม่ภายหลัง",
                )
                return redirect("setup_mfa")

    provisioning_uri = pyotp.TOTP(secret).provisioning_uri(
        name=request.user.email or request.user.username,
        issuer_name="LearnLink",
    )

    qr_image = qrcode.make(provisioning_uri)
    image_buffer = BytesIO()
    qr_image.save(image_buffer, format="PNG")

    qr_code_data_uri = (
        "data:image/png;base64,"
        + base64.b64encode(image_buffer.getvalue()).decode("ascii")
    )

    response = render(
        request,
        "users/setup_mfa.html",
        {
            "qr_code_data_uri": qr_code_data_uri,
            "secret": secret,
        },
    )
    response["Cache-Control"] = "no-store"
    return response



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

    if request.method != "POST":
        try:
            failed_attempts = get_mfa_attempts(cache_key)
        except Exception:
            messages.error(
                request,
                "ระบบยืนยันตัวตนขัดข้อง กรุณาลองใหม่ภายหลัง",
            )
            return redirect("home")

        if failed_attempts >= 5:
            request.session.pop("mfa_pending_user_id", None)
            messages.error(
                request,
                "ยืนยัน OTP ไม่สำเร็จเกินจำนวนครั้งที่กำหนด กรุณาเข้าสู่ระบบใหม่",
            )
            return redirect("home")

        return render(request, "users/verify_mfa.html")

    try:
        reserved = reserve_mfa_attempt(cache_key)
    except Exception:
        messages.error(
            request,
            "ระบบยืนยันตัวตนขัดข้อง กรุณาลองใหม่ภายหลัง",
        )
        return redirect("home")

    if not reserved:
        request.session.pop("mfa_pending_user_id", None)
        messages.error(
            request,
            "ยืนยัน OTP ไม่สำเร็จเกินจำนวนครั้งที่กำหนด กรุณาเข้าสู่ระบบใหม่",
        )
        return redirect("home")

    otp = request.POST.get("otp", "").strip()

    try:
        secret = decrypt_mfa_secret(user.mfa_secret_encrypted)
    except (ValueError, ImproperlyConfigured):
        try:
            release_mfa_attempt(cache_key)
        except Exception:
            pass

        request.session.pop("mfa_pending_user_id", None)
        messages.error(
            request,
            "ระบบยืนยันตัวตนขัดข้อง กรุณาติดต่อผู้ดูแลระบบ",
        )
        return redirect("home")

    totp = pyotp.TOTP(secret)

    matched_step = None

    if len(otp) == 6 and otp.isdigit():
        current_step = totp.timecode(timezone.now())

        for step in (current_step - 1, current_step, current_step + 1):
            if step < 0:
                continue

            if hmac.compare_digest(totp.at(step * totp.interval), otp):
                matched_step = step
                break

    if matched_step is None:
        try:
            failed_attempts = get_mfa_attempts(cache_key)
        except Exception:
            messages.error(
                request,
                "ระบบยืนยันตัวตนขัดข้อง กรุณาลองใหม่ภายหลัง",
            )
            return redirect("home")

        if failed_attempts >= 5:
            request.session.pop("mfa_pending_user_id", None)
            messages.error(
                request,
                "ยืนยัน OTP ไม่สำเร็จครบ 5 ครั้ง กรุณาเข้าสู่ระบบใหม่",
            )
            return redirect("home")

        messages.error(request, "รหัส OTP ไม่ถูกต้อง")
        return render(request, "users/verify_mfa.html")

    try:
        with transaction.atomic():
            locked_user = User.objects.select_for_update().get(
                pk=user.pk,
                mfa_enabled=True,
            )

            if matched_step <= (
                locked_user.mfa_last_used_step
                if locked_user.mfa_last_used_step is not None
                else -1
            ):
                raise ValueError("OTP has already been used")

            locked_user.mfa_last_used_step = matched_step
            locked_user.save(update_fields=["mfa_last_used_step"])

    except ValueError:
        try:
            release_mfa_attempt(cache_key)
        except Exception:
            pass

        messages.error(request, "รหัส OTP นี้ถูกใช้ไปแล้ว กรุณารอรหัสใหม่")
        return render(request, "users/verify_mfa.html")

    except User.DoesNotExist:
        try:
            release_mfa_attempt(cache_key)
        except Exception:
            pass

        request.session.pop("mfa_pending_user_id", None)
        return redirect("home")

    except Exception:
        try:
            release_mfa_attempt(cache_key)
        except Exception:
            pass

        messages.error(
            request,
            "ระบบยืนยันตัวตนขัดข้อง กรุณาลองใหม่ภายหลัง",
        )
        return redirect("home")

    try:
        release_mfa_attempt(cache_key)
    except Exception:
        messages.error(
            request,
            "ระบบยืนยันตัวตนขัดข้อง กรุณาลองใหม่ภายหลัง",
        )
        return redirect("home")

    request.session.pop("mfa_pending_user_id", None)
    login(request, user)
    return redirect("home")




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