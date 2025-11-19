# plan/views.py
from __future__ import annotations
from datetime import date, timedelta
from typing import List, Tuple
import json
import random

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST
from django.utils import timezone

from budgets.models import BudgetSpend, DailyBudget, MealPlan
from menus.models import Menu, Restaurant
from menus.utils import filter_by_plan


# ----------------- helpers -----------------
def _parse_int(v, default: int) -> int:
    try:
        return int(v)
    except Exception:
        return default


def _parse_date(s: str | None) -> date:
    if not s:
        return timezone.localdate()
    try:
        return date.fromisoformat(s)
    except Exception:
        return timezone.localdate()


# ----------------- views -----------------
@login_required
def plan_start(request):
    """เริ่มวางแผนจาก popup (หน้าแรก)"""
    if request.method == "POST":
        days = _parse_int(request.POST.get("days", "1"), 1)
        budget = _parse_int(request.POST.get("budget", "50"), 50)
        start_date = _parse_date(request.POST.get("start_date", ""))

        old = request.session.get("plan", {})
        request.session["plan"] = {
            "days": days,
            "budget": budget,
            "start_date": start_date.isoformat(),
            "allergies": old.get("allergies", []),
            "dislikes": old.get("dislikes", []),
            "religions": old.get("religions", []),
            "extra": old.get("extra", {}),
        }
        request.session.modified = True
        return redirect("plan:diet")

    return redirect("plan:diet")


@login_required
def plan_diet(request):
    """หน้าเลือกข้อจำกัดอาหาร"""
    plan = request.session.get(
        "plan",
        {"days": 1, "budget": 50, "start_date": timezone.localdate().isoformat()},
    )

    allergy_choices = ["กุ้ง", "นม", "แป้งสาลี", "ไข่", "ถั่ว", "ทะเล"]
    dislike_choices = ["หมู", "ไก่", "เห็ด", "หัวหอม", "เครื่องใน", "ผักชี", "กระเทียม", "เนื้อวัว"]
    religion_choices = ["ฮาลาล", "มังสวิรัติ", "อาหารเจ", "หลีกเลี่ยงแอลกอฮอล์"]

    if request.method == "POST":
        allergies = request.POST.getlist("allergies")
        dislikes = request.POST.getlist("dislikes")
        religions = request.POST.getlist("religions")

        request.session["plan"].update(
            {
                "allergies": allergies,
                "dislikes": dislikes,
                "religions": religions,
                "extra": {
                    "allergy": request.POST.get("extra_allergy", "").strip(),
                    "dislike": request.POST.get("extra_dislike", "").strip(),
                    "religion": request.POST.get("extra_religion", "").strip(),
                },
            }
        )
        request.session.modified = True
        return redirect("plan:summary")

    return render(
        request,
        "plan/plan_diet.html",
        {
            "plan": plan,
            "allergy_choices": allergy_choices,
            "dislike_choices": dislike_choices,
            "religion_choices": religion_choices,
        },
    )


@login_required
def mealplan_summary(request):
    """
    หน้าสรุปแผน: สุ่มร้าน -> ดึงเมนูของร้าน
    ฝั่ง JS จะเก็บเมนูที่เลือกไว้ใน localStorage ชื่อ 'mm_plan_selected'
    ทำให้กลับเข้าหน้านี้แล้วรายการที่เลือกก่อนหน้ายังอยู่
    """
    plan = request.session.get("plan")
    if not plan:
        messages.info(request, "กรุณาเริ่มวางแผนก่อน")
        return redirect("plan:start")

    budget = _parse_int(plan.get("budget", 0), 0)

    # สุ่มร้าน 3 ร้าน
    all_ids = list(Restaurant.objects.values_list("id", flat=True))
    picked_ids = random.sample(all_ids, min(3, len(all_ids)))
    restaurants = Restaurant.objects.filter(id__in=picked_ids)

    data: List[Tuple[Restaurant, List[Menu]]] = []
    for r in restaurants:
        menus = Menu.objects.filter(restaurant=r)
        menus = filter_by_plan(menus, plan)  # กรองเมนูตามข้อจำกัด
        if budget > 0:
            menus = menus.filter(price__lte=budget)
        data.append((r, list(menus)))

    return render(
        request,
        "plan/summary.html",
        {
            "plan": plan,
            "restaurant_menus": data,
            "meal_choices": ["มื้อเช้า", "มื้อเที่ยง", "มื้อเย็น"],
            "today": timezone.localdate(),
        },
    )


@login_required
@require_POST
def save_plan(request):
    """
    รับ selections จาก summary (JSON: [{id, name, price, meal, ...}, ...])
    -> สร้าง MealPlan ใหม่เสมอ
    -> สร้าง DailyBudget เฉพาะวันในช่วง (ไม่ซ้ำ)
    -> บันทึก BudgetSpend ผูกแผน

    เพิ่มเติม:
    - ตรวจสอบว่า 'ราคารวม' ไม่เกิน budget ที่ตั้งไว้
      ถ้าเกินจะไม่บันทึก และเด้งกลับหน้า summary
    """
    try:
        menus = json.loads(request.POST.get("menus", "[]"))
    except json.JSONDecodeError:
        menus = []

    if not menus:
        messages.error(request, "กรุณาเลือกเมนูก่อนบันทึก")
        return redirect("plan:summary")

    sess = request.session.get("plan") or {}
    start_date = _parse_date(sess.get("start_date"))
    days = _parse_int(sess.get("days", 1), 1)
    budget = _parse_int(sess.get("budget", 0), 0)

    # 0) ตรวจสอบ 'ราคารวม' ไม่เกินงบ
    total_price = 0
    for m in menus:
        try:
            price = int(m.get("price", 0))
        except Exception:
            price = 0
        total_price += price

    if budget > 0 and total_price > budget:
        over = total_price - budget
        messages.error(
            request,
            f"ราคารวม {total_price} บาท เกินงบ {budget} บาท (เกิน {over} บาท) กรุณาลดเมนูในแผนก่อนบันทึก",
        )
        return redirect("plan:summary")

    # 1) สร้างแผนใหม่เสมอ
    plan_obj = MealPlan.objects.create(
        user=request.user,
        start_date=start_date,
        days=days,
        budget_per_day=budget,
        title=sess.get("title", ""),
    )
    request.session["active_plan_id"] = plan_obj.id
    request.session.modified = True

    # 2) สร้าง DailyBudget ให้ครบตามจำนวนวัน
    for i in range(days):
        d = start_date + timedelta(days=i)
        DailyBudget.objects.update_or_create(
            user=request.user,
            date=d,
            plan=plan_obj,
            defaults={"amount": budget},
        )

    # 3) บันทึก BudgetSpend ตามเมนูที่เลือก
    for m in menus:
        try:
            menu = Menu.objects.get(pk=m["id"])
        except (KeyError, Menu.DoesNotExist):
            continue

        BudgetSpend.objects.create(
            user=request.user,
            date=start_date,
            amount=menu.price,
            menu=menu,
            plan=plan_obj,
            note=(m.get("meal") or ""),
        )

    messages.success(request, "บันทึกแผนเรียบร้อยแล้ว")
    return redirect("/budget/?from_plan=1")
