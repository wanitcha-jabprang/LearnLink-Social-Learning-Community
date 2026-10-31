from django.urls import path
from . import views

urlpatterns = [
    path("", views.community_list, name="community"),
    path("create/", views.create_community, name="create_community"),
    path("join/", views.join_community_by_code, name="join_community_by_code"),
    path("<int:community_id>/join/", views.join_community, name="join_community"),
    path("<int:community_id>/leave/", views.leave_community, name="leave_community"),
    path("<int:community_id>/edit/", views.edit_community, name="edit_community"),
    path("<int:community_id>/delete/", views.delete_community, name="delete_community"),
    path("<int:community_id>/transfer-ownership/", views.transfer_ownership, name="transfer_ownership"),
    path("<int:community_id>/members/<int:user_id>/remove/", views.remove_member, name="remove_member"),
    path("<int:id>/", views.community_detail, name="community_detail"),
]