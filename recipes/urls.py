from django.urls import path
from .views import recipe_list, add_recipe, edit_recipe, delete_recipe

urlpatterns = [
    path('',                recipe_list,   name='recipe_list'),
    path('add/',            add_recipe,    name='add_recipe'),
    path('edit/<int:pk>/',  edit_recipe,   name='edit_recipe'),
    path('delete/<int:pk>/',delete_recipe, name='delete_recipe'),
]
