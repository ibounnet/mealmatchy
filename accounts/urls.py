# accounts/urls.py
from django.urls import path
from .views import (
    home_view, register_view, login_view, logout_view,
    profile_view,
    plan_start,    # ✅ มีจริงใน views
    plan_diet,     # ✅ มีจริงใน views
)

urlpatterns = [
    path('home/', home_view, name='home'),

    path('register/', register_view, name='register'),
    path('login/',    login_view,    name='login'),
    path('logout/',   logout_view,   name='logout'),

    path('profile/', profile_view, name='profile'),

    # วางแผนมื้ออาหาร
    path('plan/start/', plan_start, name='plan_start'),
    path('plan/diet/',  plan_diet,  name='plan_diet'),
]
