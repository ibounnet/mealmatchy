from django.urls import path
from . import views

app_name = 'menus'

urlpatterns = [
    path('', views.menu_list, name='menu_list'),
    path('add/', views.add_menu, name='add_menu'),
    path('<int:pk>/edit/', views.edit_menu, name='edit_menu'),
    path('<int:pk>/delete/', views.delete_menu, name='delete_menu'),

    # Admin review/approval
    path('admin/', views.admin_menu_list, name='admin_menu_list'),
    path('admin/<int:pk>/edit/', views.admin_edit_menu, name='admin_edit_menu'),
    path('admin/<int:pk>/delete/', views.admin_delete_menu, name='admin_delete_menu'),
    path('admin/<int:pk>/approve/', views.approve_menu, name='approve_menu'),
    path('admin/<int:pk>/reject/', views.reject_menu, name='reject_menu'),

    # Add menu directly to a restaurant
    path('restaurant/<int:pk>/add-menu/', views.add_menu_to_restaurant, name='add_menu_to_restaurant'),
]
