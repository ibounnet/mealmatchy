# accounts/urls.py
from django.urls import path
from .views import (
    home_view, register_view, login_view, logout_view,
    profile_view, profile_remove_image_view,
)

app_name = "accounts"

urlpatterns = [
    path("home/", home_view, name="accounts_home"),

    path("register/", register_view, name="register"),
    path("login/",    login_view,    name="login"),
    path("logout/",   logout_view,   name="logout"),

    path("profile/", profile_view, name="profile"),
    path("profile/remove-image/", profile_remove_image_view, name="profile_remove_image"),
]
