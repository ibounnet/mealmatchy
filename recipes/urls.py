# recipes/urls.py
from django.urls import path
from . import views

app_name = "recipes"

urlpatterns = [

    path("mine/", views.my_recipe_list, name="mine"),  # สูตรของฉัน

    path("", views.recipe_list, name="list"),
    path("<int:pk>/", views.recipe_detail, name="detail"),
    path("add/", views.add_recipe, name="add"),
    path("<int:pk>/edit/", views.edit_recipe, name="edit"),
    path("<int:pk>/delete/", views.delete_recipe, name="delete"),  # ปุ่มลบ
]
   