from django.urls import path
from .views import admin_delete_menu, admin_edit_menu, admin_menu_list, menu_list, add_menu, edit_menu, delete_menu

urlpatterns = [
    path('',           menu_list,  name='menu_list'),
    path('add/',       add_menu,   name='add_menu'),
    path('edit/<int:pk>/',   edit_menu,  name='edit_menu'),
    path('delete/<int:pk>/', delete_menu, name='delete_menu'),

    # ฝั่งแอดมิน (ใหม่)
    path('admin/',                 admin_menu_list,   name='admin_menu_list'),
    path('admin/edit/<int:pk>/',   admin_edit_menu,   name='admin_edit_menu'),
    path('admin/delete/<int:pk>/', admin_delete_menu, name='admin_delete_menu'),

]
