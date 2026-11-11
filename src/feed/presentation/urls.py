from django.urls import path
from . import views

urlpatterns = [
    path("", views.home_view, name="home"),
    path("explore/", views.explore_view, name="explore"),
]