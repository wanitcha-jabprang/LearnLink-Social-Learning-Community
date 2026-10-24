import json
from functools import wraps

from django.contrib import messages
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST
from PIL import Image, UnidentifiedImageError

from .models import Bookmark, Comment, Like, Post


MAX_IMAGE_SIZE = 10 * 1024 * 1024
MAX_VIDEO_SIZE = 100 * 1024 * 1024


def _request_data(request):
    if request.content_type == "application/json":
        try:
            return json.loads(request.body)
        except (json.JSONDecodeError, UnicodeDecodeError):
            return None
    return request.POST


def _error(message, status=400):
    return JsonResponse({"error": message}, status=status)


def _is_html_form(request):
    return request.POST.get("_html") == "1"


def _form_response(request, message, *, error=False):
    if not _is_html_form(request):
        return None
    if error:
        messages.error(request, message)
    else:
        messages.success(request, message)
    destination = request.POST.get("next", "/#home-page")
    if not url_has_allowed_host_and_scheme(
        destination,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        destination = "/#home-page"
    return redirect(destination)


def _error_response(request, message, status=400):
    return _form_response(request, message, error=True) or _error(message, status)


def _require_authentication(view):
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return _error("กรุณาเข้าสู่ระบบก่อนดำเนินการ", 401)
        return view(request, *args, **kwargs)

    return wrapped


def _post_payload(post):
    return {
        "id": post.pk,
        "content": post.content,
        "author": post.user.full_name or post.user.username,
        "community": post.community.name if post.community_id else "",
        "created_at": post.created_at.isoformat(),
        "image_url": post.image.url if post.image else "",
        "video_url": post.video.url if post.video else "",
        "likes_count": post.like_set.count(),
        "comments_count": post.comment_set.count(),
    }


def _validate_image(image):
    if not image:
        return None
    if image.size > MAX_IMAGE_SIZE:
        return "รูปภาพต้องมีขนาดไม่เกิน 10 MB"
    try:
        with Image.open(image) as image_file:
            image_file.verify()
    except (Image.DecompressionBombError, UnidentifiedImageError, OSError, ValueError):
        return "ไฟล์รูปภาพไม่ถูกต้อง"
    image.seek(0)
    return None


def _validate_video(video):
    if not video:
        return None
    if video.size > MAX_VIDEO_SIZE:
        return "วิดีโอต้องมีขนาดไม่เกิน 100 MB"
    if not video.content_type or not video.content_type.startswith("video/"):
        return "กรุณาเลือกไฟล์วิดีโอ"
    return None



def _can_access_post(request, post):
    # ผู้ใช้ต้องเข้าสู่ระบบก่อน
    if not request.user.is_authenticated:
        return False

    # โพสต์สาธารณะ: ไม่มีการผูกกับกลุ่ม
    if post.community_id is None:
        return True

    community = post.community

    # เจ้าของกลุ่มเข้าถึงโพสต์ในกลุ่มได้
    if community.owner_id == request.user.pk:
        return True

    # โพสต์ในกลุ่ม: ต้องเป็นสมาชิกกลุ่มเท่านั้น
    from community.models import CommunityMember

    return CommunityMember.objects.filter(
        community_id=post.community_id,
        user_id=request.user.pk,
    ).exists()


def _private_post_error(request):
    return _error_response(request, "คุณไม่มีสิทธิ์เข้าถึงโพสต์นี้", 404)


@_require_authentication
@require_POST
def create_post(request):
    content = request.POST.get("content", "")
    if not isinstance(content, str) or not content.strip():
        return _error_response(request, "กรุณาเขียนเนื้อหาโพสต์ก่อน")
    content = content.strip()

    image = request.FILES.get("image")
    video = request.FILES.get("video")
    error = _validate_image(image) or _validate_video(video)
    if error:
        return _error_response(request, error)

    community_id = request.POST.get("community_id", "").strip()
    community = None
    if community_id:
        from community.models import Community, CommunityMember

        community = get_object_or_404(Community, pk=community_id)
        is_member = CommunityMember.objects.filter(
            community=community,
            user=request.user,
        ).exists()
        if community.owner_id != request.user.pk and not is_member:
            return _error_response(request, "คุณต้องเข้าร่วมชุมชนก่อนจึงจะโพสต์ได้", 403)

    post = Post.objects.create(
        user=request.user,
        content=content,
        image=image,
        video=video,
        community=community,
    )
    form_response = _form_response(request, "โพสต์ของคุณถูกบันทึกแล้ว")
    if form_response:
        return form_response
    return JsonResponse({"post": _post_payload(post)}, status=201)


@_require_authentication
@require_POST
def edit_post(request, post_id):
    post = get_object_or_404(Post, pk=post_id)
    if post.user_id != request.user.pk:
        return _error_response(request, "คุณไม่มีสิทธิ์แก้ไขโพสต์นี้", 403)
    data = _request_data(request)
    if not isinstance(data, dict) and not hasattr(data, "get"):
        return _error_response(request, "ข้อมูลที่ส่งมาไม่ถูกต้อง")
    content = data.get("content", "")
    if not isinstance(content, str) or not content.strip():
        return _error_response(request, "กรุณาเขียนเนื้อหาโพสต์ก่อน")
    post.content = content.strip()
    post.save(update_fields=["content"])
    form_response = _form_response(request, "แก้ไขโพสต์แล้ว")
    if form_response:
        return form_response
    return JsonResponse({"post": _post_payload(post)})


@_require_authentication
@require_POST
def delete_post(request, post_id):
    post = get_object_or_404(Post, pk=post_id)
    if post.user_id != request.user.pk:
        return _error_response(request, "คุณไม่มีสิทธิ์ลบโพสต์นี้", 403)
    image = post.image
    video = post.video
    post.delete()
    if image:
        image.delete(save=False)
    if video:
        video.delete(save=False)
    form_response = _form_response(request, "ลบโพสต์แล้ว")
    if form_response:
        return form_response
    return JsonResponse({"deleted": True})


@_require_authentication
@require_POST
def create_comment(request, post_id):
    post = get_object_or_404(Post, pk=post_id)
    if not _can_access_post(request, post):
        return _private_post_error(request)
    data = _request_data(request)
    if not isinstance(data, dict) and not hasattr(data, "get"):
        return _error_response(request, "ข้อมูลที่ส่งมาไม่ถูกต้อง")
    content = data.get("content", "")
    if not isinstance(content, str) or not content.strip():
        return _error_response(request, "กรุณาเขียนความคิดเห็นก่อน")
    comment = Comment.objects.create(post=post, user=request.user, content=content.strip())
    form_response = _form_response(request, "เพิ่มความคิดเห็นแล้ว")
    if form_response:
        return form_response
    return JsonResponse(
        {
            "comment": {
                "id": comment.pk,
                "content": comment.content,
                "author": comment.user.full_name or comment.user.username,
                "created_at": comment.created_at.isoformat(),
            },
            "comments_count": post.comment_set.count(),
        },
        status=201,
    )


@_require_authentication
@require_POST
def edit_comment(request, comment_id):
    comment = get_object_or_404(Comment, pk=comment_id)
    if not _can_access_post(request, comment.post):
        return _private_post_error(request)
    if comment.user_id != request.user.pk:
        return _error_response(request, "คุณไม่มีสิทธิ์แก้ไขความคิดเห็นนี้", 403)
    data = _request_data(request)
    if not isinstance(data, dict) and not hasattr(data, "get"):
        return _error_response(request, "ข้อมูลที่ส่งมาไม่ถูกต้อง")
    content = data.get("content", "")
    if not isinstance(content, str) or not content.strip():
        return _error_response(request, "กรุณาเขียนความคิดเห็นก่อน")
    comment.content = content.strip()
    comment.save(update_fields=["content"])
    form_response = _form_response(request, "แก้ไขความคิดเห็นแล้ว")
    if form_response:
        return form_response
    return JsonResponse({"comment": {"id": comment.pk, "content": comment.content}})


@_require_authentication
@require_POST
def delete_comment(request, comment_id):
    comment = get_object_or_404(Comment, pk=comment_id)
    if not _can_access_post(request, comment.post):
        return _private_post_error(request)
    if comment.user_id != request.user.pk:
        return _error_response(request, "คุณไม่มีสิทธิ์ลบความคิดเห็นนี้", 403)
    comment.delete()
    form_response = _form_response(request, "ลบความคิดเห็นแล้ว")
    if form_response:
        return form_response
    return JsonResponse({"deleted": True})


@_require_authentication
@require_POST
def toggle_like(request, post_id):
    post = get_object_or_404(Post, pk=post_id)
    if not _can_access_post(request, post):
        return _private_post_error(request)
    like, created = Like.objects.get_or_create(post=post, user=request.user)
    if not created:
        like.delete()
    return _form_response(
        request,
        "ถูกใจโพสต์แล้ว" if created else "นำการถูกใจออกแล้ว",
    ) or JsonResponse({"liked": created})


@_require_authentication
@require_POST
def toggle_bookmark(request, post_id):
    post = get_object_or_404(Post, pk=post_id)
    if not _can_access_post(request, post):
        return _private_post_error(request)
    bookmark, created = Bookmark.objects.get_or_create(post=post, user=request.user)
    if not created:
        bookmark.delete()
    return _form_response(
        request,
        "บันทึกโพสต์แล้ว" if created else "นำโพสต์ออกจากรายการบันทึกแล้ว",
    ) or JsonResponse({"saved": created})
