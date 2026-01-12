# plan/urls.py
from django.urls import path
from . import views

app_name = "plan"

urlpatterns = [
    path("start/",   views.plan_start,         name="start"),
    path("diet/",    views.plan_diet,          name="diet"),
    path("summary/", views.mealplan_summary,   name="summary"),
    path("save/",    views.save_plan,          name="save_plan"),

    # เพิ่มใหม่: รายการแผน + สลับแผนที่ใช้งานอยู่
    path("my-plans/", views.my_plans,          name="my_plans"),
    path("use/<int:plan_id>/", views.use_plan, name="use_plan"),
]
