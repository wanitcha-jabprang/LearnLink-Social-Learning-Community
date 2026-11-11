import json
from functools import wraps

from django.contrib import messages
from django.http import JsonResponse
from django.shortcuts import redirect
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from post.infrastructure.container import get_post_services


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
    return _form_response(request, message, error=True) or _error(
        message, status
    )


def _require_authentication(view):
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return _error("กรุณาเข้าสู่ระบบก่อนดำเนินการ", 401)
        return view(request, *args, **kwargs)

    return wrapped


def _service_error(request, error, *, permission_status=403):
    if isinstance(error, PermissionError):
        status = (
            404 if str(error) == "คุณไม่มีสิทธิ์เข้าถึงโพสต์นี้" else permission_status
        )
    elif isinstance(error, LookupError):
        status = 404
    else:
        status = 400
    return _error_response(request, str(error), status)


@_require_authentication
@require_POST
def create_post(request):
    community_id = request.POST.get("community_id", "").strip()
    services = get_post_services()
    try:
        post = services.posts.create(
            request.user,
            content=request.POST.get("content", ""),
            image=request.FILES.get("image"),
            video=request.FILES.get("video"),
            community_id=community_id or None,
        )
    except (ValueError, PermissionError, LookupError) as error:
        return _service_error(request, error)
    form_response = _form_response(request, "โพสต์ของคุณถูกบันทึกแล้ว")
    if form_response:
        return form_response
    return JsonResponse(
        {
            "post": services.posts.payload(
                post,
                comments_count=services.comments.count_for_post(post),
            )
        },
        status=201,
    )


@_require_authentication
@require_POST
def edit_post(request, post_id):
    data = _request_data(request)
    if not isinstance(data, dict) and not hasattr(data, "get"):
        return _error_response(request, "ข้อมูลที่ส่งมาไม่ถูกต้อง")
    services = get_post_services()
    try:
        post = services.posts.edit(
            post_id, request.user, data.get("content", "")
        )
    except (ValueError, PermissionError, LookupError) as error:
        return _service_error(request, error)
    form_response = _form_response(request, "แก้ไขโพสต์แล้ว")
    if form_response:
        return form_response
    return JsonResponse(
        {
            "post": services.posts.payload(
                post,
                comments_count=services.comments.count_for_post(post),
            )
        }
    )


@_require_authentication
@require_POST
def delete_post(request, post_id):
    services = get_post_services()
    try:
        services.posts.delete(post_id, request.user)
    except (PermissionError, LookupError) as error:
        return _service_error(request, error)
    form_response = _form_response(request, "ลบโพสต์แล้ว")
    if form_response:
        return form_response
    return JsonResponse({"deleted": True})


@_require_authentication
@require_POST
def create_comment(request, post_id):
    data = _request_data(request)
    if not isinstance(data, dict) and not hasattr(data, "get"):
        return _error_response(request, "ข้อมูลที่ส่งมาไม่ถูกต้อง")
    services = get_post_services()
    try:
        comment, post = services.comments.create(
            post_id,
            request.user,
            data.get("content", ""),
        )
    except (ValueError, PermissionError, LookupError) as error:
        return _service_error(request, error)
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
            "comments_count": services.comments.count_for_post(post),
        },
        status=201,
    )


@_require_authentication
@require_POST
def edit_comment(request, comment_id):
    data = _request_data(request)
    if not isinstance(data, dict) and not hasattr(data, "get"):
        return _error_response(request, "ข้อมูลที่ส่งมาไม่ถูกต้อง")
    services = get_post_services()
    try:
        comment = services.comments.edit(
            comment_id,
            request.user,
            data.get("content", ""),
        )
    except (ValueError, PermissionError, LookupError) as error:
        return _service_error(request, error)
    form_response = _form_response(request, "แก้ไขความคิดเห็นแล้ว")
    if form_response:
        return form_response
    return JsonResponse(
        {"comment": {"id": comment.pk, "content": comment.content}}
    )


@_require_authentication
@require_POST
def delete_comment(request, comment_id):
    services = get_post_services()
    try:
        services.comments.delete(comment_id, request.user)
    except (PermissionError, LookupError) as error:
        return _service_error(request, error)
    form_response = _form_response(request, "ลบความคิดเห็นแล้ว")
    if form_response:
        return form_response
    return JsonResponse({"deleted": True})


def _toggle(request, post_id, *, kind, message):
    services = get_post_services()
    try:
        created = services.interactions.toggle(kind, post_id, request.user)
    except (PermissionError, LookupError) as error:
        return _service_error(request, error)
    form_response = _form_response(
        request,
        message[0] if created else message[1],
    )
    if form_response:
        return form_response
    return JsonResponse({"liked" if kind == "like" else "saved": created})


@_require_authentication
@require_POST
def toggle_like(request, post_id):
    return _toggle(
        request,
        post_id,
        kind="like",
        message=("ถูกใจโพสต์แล้ว", "นำการถูกใจออกแล้ว"),
    )


@_require_authentication
@require_POST
def toggle_bookmark(request, post_id):
    return _toggle(
        request,
        post_id,
        kind="bookmark",
        message=("บันทึกโพสต์แล้ว", "นำโพสต์ออกจากรายการบันทึกแล้ว"),
    )
