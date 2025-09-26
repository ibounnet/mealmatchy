from django.urls import path
from . import views

app_name = "plan"

urlpatterns = [
    path("start/",   views.plan_start,   name="start"),
    path("diet/",    views.plan_diet,    name="diet"),
    path("summary/", views.mealplan_summary, name="summary"),

]

