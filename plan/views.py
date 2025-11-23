# plan/views.py
from __future__ import annotations

import json
import random
from datetime import date, timedelta
from typing import List, Tuple

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

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
    """
    เริ่มวางแผนจาก popup (หน้าแรก)

    - ทุกครั้งที่เริ่มแผนใหม่ ให้รีเซ็ต selections เก่าออกจาก session
    - เก็บเฉพาะ preference (ข้อจำกัดอาหาร) ไว้ต่อได้ถ้าต้องการ
    """
    if request.method == "POST":
        days = _parse_int(request.POST.get("days", "1"), 1)
        budget = _parse_int(request.POST.get("budget", "50"), 50)
        start_date = _parse_date(request.POST.get("start_date", ""))

        old = request.session.get("plan", {})

        request.session["plan"] = {
            "days": days,
            "budget": budget,
            "start_date": start_date.isoformat(),
            # ค่า preference เดิม (ไม่บังคับ)
            "allergies": old.get("allergies", []),
            "dislikes": old.get("dislikes", []),
            "religions": old.get("religions", []),
            "extra": old.get("extra", {}),
        }

        # ล้าง selection เดิม + plan เดิม
        request.session.pop("selected_menus", None)
        request.session.pop("active_plan_id", None)
        request.session.modified = True

        return redirect("plan:diet")

    # ถ้าเป็น GET ก็ถือว่าเริ่มใหม่เหมือนกัน
    request.session.pop("selected_menus", None)
    request.session.pop("active_plan_id", None)
    request.session.modified = True
    return redirect("plan:diet")


@login_required
def plan_diet(request):
    """หน้าเลือกข้อจำกัดอาหาร"""
    plan = request.session.get(
        "plan",
        {
            "days": 1,
            "budget": 50,
            "start_date": timezone.localdate().isoformat(),
        },
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
    หน้าสรุปแผน / เลือกเมนู:

    - สุ่มร้าน 3 ร้าน + ดึงเมนูตามข้อจำกัด / งบ
    - โหลด selection เก่าทั้งจาก session หรือจากฐานข้อมูล (BudgetSpend ของ active_plan)
      เพื่อให้กลับมาหน้านี้แล้วยังค้างเมนูที่เคยเลือกไว้
    """
    plan = request.session.get("plan")
    if not plan:
        messages.info(request, "กรุณาเริ่มวางแผนก่อน")
        return redirect("plan:start")

    budget = _parse_int(plan.get("budget", 0), 0)

    # สุ่มร้าน 3 ร้าน
    all_ids = list(Restaurant.objects.values_list("id", flat=True))
    picked_ids = random.sample(all_ids, min(3, len(all_ids))) if all_ids else []
    restaurants = Restaurant.objects.filter(id__in=picked_ids)

    data: List[Tuple[Restaurant, List[Menu]]] = []
    for r in restaurants:
        menus = Menu.objects.filter(restaurant=r)
        menus = filter_by_plan(menus, plan)  # กรองตามข้อจำกัด
        if budget > 0:
            menus = menus.filter(price__lte=budget)
        data.append((r, list(menus)))

    # ---------- โหลด selected_menus จาก session / DB ----------
    selected = request.session.get("selected_menus")

    # ถ้าใน session ว่าง แต่มี active_plan_id ให้ดึงจาก DB มาใช้ต่อ
    if selected is None:
        active_plan_id = request.session.get("active_plan_id")
        if active_plan_id:
            spends = (
                BudgetSpend.objects.filter(
                    user=request.user,
                    plan_id=active_plan_id,
                )
                .select_related("menu", "menu__restaurant")
                .order_by("id")
            )
            selected = []
            for s in spends:
                menu = s.menu
                selected.append(
                    {
                        "id": menu.id,
                        "name": menu.name,
                        "price": int(menu.price),
                        "image": menu.image.url if menu.image else "",
                        "restaurant": menu.restaurant_name
                        or (menu.restaurant.name if menu.restaurant else ""),
                        "meal": s.note or "",
                    }
                )

            request.session["selected_menus"] = selected
            request.session.modified = True

    if selected is None:
        selected = []

    selected_json = json.dumps(selected, ensure_ascii=False)

    return render(
        request,
        "plan/summary.html",
        {
            "plan": plan,
            "restaurant_menus": data,
            "meal_choices": ["มื้อเช้า", "มื้อเที่ยง", "มื้อเย็น"],
            "today": timezone.localdate(),
            "selected_menus_json": selected_json,
        },
    )


@login_required
@require_POST
def save_plan(request):
    """
    บันทึกแผนจากหน้า summary

    - ถ้ายังไม่มีแผน => สร้าง MealPlan ใหม่
    - ถ้ามีแผนอยู่แล้วใน session (active_plan_id) => แก้ไขแผนนั้น
    - สำหรับช่วงวันที่ของแผน: ลบ BudgetSpend เดิมของแผนนี้ก่อน แล้วค่อยสร้างใหม่
      ทำให้เวลาบันทึกซ้ำ ยอด 'ใช้ไป' ไม่ถูกนับซ้ำ
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

    # -------------------------------
    # 1) หา / สร้าง MealPlan
    # -------------------------------
    plan_obj = None
    plan_id = request.session.get("active_plan_id")

    if plan_id:
        try:
            plan_obj = MealPlan.objects.get(id=plan_id, user=request.user)
            # อัปเดตข้อมูลล่าสุดของแผน
            plan_obj.start_date = start_date
            plan_obj.days = days
            plan_obj.budget_per_day = budget
            plan_obj.title = sess.get("title", "") or plan_obj.title
            plan_obj.save()
        except MealPlan.DoesNotExist:
            plan_obj = None

    if plan_obj is None:
        plan_obj = MealPlan.objects.create(
            user=request.user,
            start_date=start_date,
            days=days,
            budget_per_day=budget,
            title=sess.get("title", ""),
        )

    # เก็บ id แผนตัวที่ใช้อยู่ใน session
    request.session["active_plan_id"] = plan_obj.id
    request.session.modified = True

    # -------------------------------
    # 2) อัปเดต DailyBudget ของช่วงวันแผน
    # -------------------------------
    date_list = []
    for i in range(days):
        d = start_date + timedelta(days=i)
        date_list.append(d)
        DailyBudget.objects.update_or_create(
            user=request.user,
            date=d,
            defaults={
                "amount": budget,
                "plan": plan_obj,
            },
        )

    # -------------------------------
    # 3) ลบ BudgetSpend เดิมของแผนนี้ในช่วงวัน แล้วสร้างใหม่
    #    (ป้องกันใช้ไปถูกบวกซ้ำ ๆ เวลาแก้แผน)
    # -------------------------------
    BudgetSpend.objects.filter(
        user=request.user,
        plan=plan_obj,
        date__in=date_list,
    ).delete()

    for m in menus:
        try:
            menu = Menu.objects.get(pk=m["id"])
        except (Menu.DoesNotExist, KeyError):
            continue

        # ตอนนี้ทุกเมนูผูกกับวันเริ่มต้น (1 วัน)
        spend_date = start_date
        BudgetSpend.objects.create(
            user=request.user,
            date=spend_date,
            amount=menu.price,
            menu=menu,
            plan=plan_obj,
            note=m.get("meal") or "",
        )

    messages.success(request, "บันทึกแผนเรียบร้อยแล้ว")
    return redirect("/budget/?from_plan=1")