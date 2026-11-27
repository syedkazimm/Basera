from django.urls import path

from . import views

urlpatterns = [
    path("seller/plants/add/", views.add_listing, name="listing_add"),
    path("plants/<int:pk>/", views.plant_detail, name="plant_detail"),
]
