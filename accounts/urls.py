# accounts/urls.py
from django.urls import path
from .views import (
    home_view, register_view, login_view, logout_view,
    profile_view,
)

urlpatterns = [
    # ถ้าอยากให้ /accounts/home/ ยังใช้ได้ ให้เปลี่ยนชื่อเป็น accounts_home
    path('home/', home_view, name='accounts_home'),

    path('register/', register_view, name='register'),
    path('login/',    login_view,    name='login'),
    path('logout/',   logout_view,   name='logout'),

    path('profile/', profile_view, name='profile'),
]
