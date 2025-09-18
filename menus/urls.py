# menus/urls.py
from django.urls import path
from . import views

app_name = 'menus'  # << สำคัญ

urlpatterns = [
    path('', views.menu_list, name='menu_list'),
    path('add/', views.add_menu, name='add_menu'),
    path('edit/<int:pk>/', views.edit_menu, name='edit_menu'),
    path('delete/<int:pk>/', views.delete_menu, name='delete_menu'),

    # สำหรับแอดมิน
    path("admin/", views.admin_menu_list, name="admin_menu_list"),
    path("admin/edit/<int:pk>/", views.admin_edit_menu, name="admin_edit_menu"),
    path("admin/delete/<int:pk>/", views.admin_delete_menu, name="admin_delete_menu"),

    # ผูกเมนูเข้าร้าน
    path('restaurant/<int:pk>/add/', views.add_menu_to_restaurant, name='add_menu_to_restaurant'),

    # อนุมัติ/ปฏิเสธ
    path('approve/<int:pk>/', views.approve_menu, name='approve_menu'),
    path('reject/<int:pk>/', views.reject_menu, name='reject_menu'),
]
