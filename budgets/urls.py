from django.urls import path
from . import views

app_name = "budgets"

urlpatterns = [
    # ตารางงบรายสัปดาห์ (หน้าแรกของ budgets)
    path("budget/", views.budget_table, name="home"),

    # Dashboard สรุป 7 วัน
    path("budget/summary/", views.weekly_summary, name="weekly_summary"),

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

    # alias (รองรับโค้ดเก่า/เส้นทางเก่า)
    path("budget/save-expense/", views.save_expense, name="save_expense"),
    path("budget/save-menu-expense/<int:menu_id>/", views.save_menu_expense, name="save_menu_expense"),
]
