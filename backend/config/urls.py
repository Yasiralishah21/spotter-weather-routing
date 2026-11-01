from django.urls import path

from routing import views

urlpatterns = [
    path("api/health/", views.health),
    path("api/geocode/", views.geocode),
    path("api/analyze/", views.analyze),
]
