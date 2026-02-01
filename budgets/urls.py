# budgets/urls.py
from django.urls import path
from . import views

app_name = "budgets"

urlpatterns = [
    # ตารางงบรายสัปดาห์/รายวัน (หน้าแรก budgets)
    path("budget/", views.budget_table, name="home"),

    # สรุป 7 วัน (แบบเดิม)
    path("budget/summary/", views.weekly_summary, name="weekly_summary"),

    # Dashboard (ไฟล์ใหม่ที่คุณทำไว้)
    path("dashboard/", views.dashboard, name="dashboard"),

    # ตั้ง/แก้งบรายวัน
    path("budget/set/", views.set_daily_budget, name="set_daily"),
    path("budget/set/<slug:date_str>/", views.set_daily_budget, name="set_daily_with_date"),

    # ดูรายละเอียดรายวัน
    path("budget/day/<slug:date_str>/", views.day_detail, name="day_detail"),

    # บันทึกค่าใช้จ่าย
    path("budget/consume/menu/<int:menu_id>/", views.consume_menu, name="consume_menu"),
    path("budget/consume/outside/", views.consume_outside, name="consume_outside"),
    path("budget/delete/<int:pk>/", views.delete_spend, name="delete_spend"),

    # ตั้งงบเท่ากันทั้งสัปดาห์
    path("budget/set-week/", views.set_week_same_amount, name="set_week_same_amount"),

    # alias (รองรับโค้ดเก่า)
    path("budget/save-expense/", views.save_expense, name="save_expense"),
    path("budget/save-menu-expense/<int:menu_id>/", views.save_menu_expense, name="save_menu_expense"),

    path("recipe/add/<int:recipe_id>/", views.add_recipe_to_day, name="add_recipe_to_day"),
]


