from django.urls import path
from . import views

urlpatterns = [
    path("login/", views.login_view, name="login"),
    path("register/", views.register_view, name="register"),
    path("logout/", views.logout_view, name="logout"),
    path("profile/", views.profile_view, name="profile"),
    path("profile/edit/", views.edit_profile_view, name="edit_profile"),
    path("profile/cover/", views.update_profile_cover_view, name="update_profile_cover"),
    path("profile/delete/", views.delete_account_view, name="delete_account"),
    path("profile/<int:user_id>/follow/", views.follow_view, name="follow"),
    path("profile/<int:user_id>/unfollow/", views.unfollow_view, name="unfollow"),
]
