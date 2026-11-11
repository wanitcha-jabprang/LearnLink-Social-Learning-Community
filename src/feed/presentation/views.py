from django.shortcuts import render

from feed.infrastructure.container import get_feed_service


def home_view(request):
    context = get_feed_service().home_context(
        request.user,
        request.GET.get("q", ""),
        request.GET.get("saved") == "1",
    )
    return render(request, "home/home.html", context)


def explore_view(request):
    return home_view(request)
