from django.shortcuts import render

from core.application.services import HomePageService


def home(request):
    return render(request, "home/home.html", HomePageService().context())
