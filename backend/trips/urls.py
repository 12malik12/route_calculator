from django.urls import path

from . import views

urlpatterns = [
    # Register both with and without a trailing slash so a POST never triggers
    # Django's APPEND_SLASH redirect (which 500s because it can't preserve the body).
    path("trip/calculate/", views.calculate_trip, name="calculate_trip"),
    path("trip/calculate", views.calculate_trip, name="calculate_trip_no_slash"),
]
