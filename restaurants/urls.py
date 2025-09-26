from django.urls import path
from . import views

app_name = "restaurants"

urlpatterns = [
    # ผู้ใช้ทั่วไป
    path("", views.restaurant_list, name="restaurant_list"),
    path("<int:pk>/", views.restaurant_detail, name="restaurant_detail"),
    path("request/", views.request_new_restaurant, name="request_new_restaurant"),

    # แอดมิน
    path("admin/list/", views.admin_restaurant_list, name="admin_restaurant_list"),
    path("admin/add/", views.admin_add_restaurant, name="admin_add_restaurant"),
    path("admin/<int:pk>/edit/", views.admin_edit_restaurant, name="admin_edit_restaurant"),
    path("admin/<int:pk>/delete/", views.admin_delete_restaurant, name="admin_delete_restaurant"),
    path("admin/<int:pk>/approve/", views.admin_approve_restaurant, name="admin_approve_restaurant"),
    path("admin/<int:pk>/reject/", views.admin_reject_restaurant, name="admin_reject_restaurant"),
]
