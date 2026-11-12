from django.urls import path

from . import views

urlpatterns = [
    path("", views.home_view, name="home"),
    path("explore/", views.explore_view, name="explore"),
    path("post/<int:post_id>/report/", views.report_post_view, name="report_post"),
]