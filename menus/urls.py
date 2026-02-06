# menus/urls.py
from django.urls import path
from . import views

app_name = "menus"

urlpatterns = [
    # ผู้ใช้ทั่วไป (เห็นเฉพาะ APPROVED)
    path("", views.menu_list, name="menu_list"),
    path("<int:pk>/", views.menu_detail, name="menu_detail"),

    # ผู้ใช้ส่งคำขอเพิ่มเมนู (PENDING)
    path("add/", views.add_menu, name="add_menu"),
    path("edit/<int:pk>/", views.edit_menu, name="edit_menu"),
    path("delete/<int:pk>/", views.delete_menu, name="delete_menu"),

    # ผูกเมนูเข้าร้าน (ถ้าคุณใช้จริง)
    path("restaurant/<int:pk>/add/", views.add_menu_to_restaurant, name="add_menu_to_restaurant"),

    # แอดมิน: จัดการคำขอเมนู
    path("admin/", views.admin_menu_list, name="admin_menu_list"),
    path("admin/<int:pk>/edit/", views.admin_edit_menu, name="admin_edit_menu"),
    path("admin/<int:pk>/delete/", views.admin_delete_menu, name="admin_delete_menu"),
    path("admin/<int:pk>/approve/", views.approve_menu, name="approve_menu"),
    path("admin/<int:pk>/reject/", views.reject_menu, name="reject_menu"),

    # แอดมิน: จัดการวัตถุดิบ (ของที่ scrape มา)
    path("admin/ingredients/", views.admin_ingredient_list, name="admin_ingredient_list"),
    path("admin/ingredients/<int:pk>/edit/", views.admin_ingredient_edit, name="admin_ingredient_edit"),
    path("admin/ingredients/<int:pk>/delete/", views.admin_ingredient_delete, name="admin_ingredient_delete"),
]
