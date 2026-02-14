from django.urls import path
from . import auth_views

urlpatterns = [
    path("signup/", auth_views.signup, name="signup"),
]
