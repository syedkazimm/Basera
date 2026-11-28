from django.urls import path

from . import views

urlpatterns = [
    path("profiles/", views.profile_list, name="grow_profiles"),
    path("profiles/new/", views.profile_create, name="grow_profile_new"),
    path("profiles/<int:pk>/edit/", views.profile_edit, name="grow_profile_edit"),
    path("profiles/<int:pk>/delete/", views.profile_delete, name="grow_profile_delete"),
]
