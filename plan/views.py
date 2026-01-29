from __future__ import annotations

from datetime import date, timedelta
from typing import List, Tuple
import json, random
from django.urls import reverse


from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render, get_object_or_404
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
        return date.fromisoformat(str(s))
    except Exception:
        return timezone.localdate()


def _plan_end_date(start: date, days: int) -> date:
    """วันสุดท้ายของแผน (inclusive)"""
    if not start:
        start = timezone.localdate()
    if not days or days <= 0:
        days = 1
    return start + timedelta(days=days - 1)


def _daily_budget(total_budget: int, days: int) -> float:
    if not days or days <= 0:
        days = 1
    if not total_budget or total_budget <= 0:
        return 0.0
    return round(total_budget / days, 2)


def _menu_date_from_payload(start_date: date, payload: dict) -> date:
    """
    รองรับ 3 แบบ:
      1) payload['date'] = 'YYYY-MM-DD'
      2) payload['day_offset'] = 0..6
      3) ไม่มี -> fallback = start_date
    """
    d = payload.get("date")
    if d:
        try:
            return date.fromisoformat(str(d))
        except Exception:
            pass

    if payload.get("day_offset") is not None:
        try:
            off = int(payload["day_offset"])
            if off < 0:
                off = 0
            return start_date + timedelta(days=off)
        except Exception:
            pass

    return start_date


def _ensure_session_plan(request):
    """
    กัน KeyError / session หาย:
    ให้มี request.session['plan'] เสมอ
    """
    if "plan" not in request.session or not isinstance(request.session.get("plan"), dict):
        request.session["plan"] = {
            "days": 7,
            "budget": 50,
            "start_date": timezone.localdate().isoformat(),
            "allergies": [],
            "dislikes": [],
            "religions": [],
            "extra": {},
        }
        request.session.modified = True
    return request.session["plan"]


def _normalize_selected_menus(menus):
    """
    ทำให้ payload จาก JS เป็นรูปแบบที่ backend ใช้ได้เสมอ
    และกันข้อมูลพัง (type/field)
    """
    if not isinstance(menus, list):
        return []

    out = []
    for m in menus:
        if not isinstance(m, dict):
            continue

        menu_id = m.get("id")
        try:
            menu_id = int(menu_id)
        except Exception:
            continue

        meal = (m.get("meal") or "").strip()
        if not meal:
            # ถ้าไม่มีมื้อ ถือว่า invalid
            continue

        # date/day_offset
        d = m.get("date")
        day_offset = m.get("day_offset")
        if day_offset is not None:
            try:
                day_offset = int(day_offset)
            except Exception:
                day_offset = None

        # key: id|date|meal (ให้ JS ส่งมาก็ได้ แต่ถ้าไม่ส่ง เราสร้างให้)
        key = (m.get("key") or "").strip()
        out.append({
            "id": menu_id,
            "meal": meal,
            "date": str(d) if d else "",
            "day_offset": day_offset,
            "key": key,  # backend ไม่บังคับ แต่เก็บไว้กันลบผิด
        })

    return out


# ----------------- views -----------------
@login_required
def plan_start(request):
    """
    เริ่มวางแผนจาก popup (หน้าแรก)
    - reset selected_menus
    - reset active_plan_id
    """
    if request.method == "POST":
        days = _parse_int(request.POST.get("days") or "7", 7)
        if days not in (1, 7):
            days = 7

        budget = _parse_int(request.POST.get("budget", "50"), 50)
        start_date = _parse_date(request.POST.get("start_date", ""))

        old = request.session.get("plan", {}) or {}

        request.session["plan"] = {
            "days": days,
            "budget": budget,  # งบรวมทั้งช่วง
            "start_date": start_date.isoformat(),
            "allergies": old.get("allergies", []),
            "dislikes": old.get("dislikes", []),
            "religions": old.get("religions", []),
            "extra": old.get("extra", {}),
        }

        request.session.pop("selected_menus", None)
        request.session.pop("active_plan_id", None)
        request.session.modified = True
        return redirect("plan:diet")

    # GET ก็ถือว่าเริ่มใหม่ (กันค้าง)
    request.session.pop("selected_menus", None)
    request.session.pop("active_plan_id", None)
    request.session.modified = True
    return redirect("plan:diet")


@login_required
def plan_diet(request):
    """หน้าเลือกข้อจำกัดอาหาร"""
    plan = _ensure_session_plan(request)

    allergy_choices  = ["กุ้ง", "นม", "แป้งสาลี", "ไข่", "ถั่ว", "ทะเล"]
    dislike_choices  = ["หมู", "ไก่", "เห็ด", "หัวหอม", "เครื่องใน", "ผักชี", "กระเทียม", "เนื้อวัว"]
    religion_choices = ["ฮาลาล", "มังสวิรัติ", "อาหารเจ", "หลีกเลี่ยงแอลกอฮอล์"]

    if request.method == "POST":
        allergies = request.POST.getlist("allergies")
        dislikes  = request.POST.getlist("dislikes")
        religions = request.POST.getlist("religions")

        plan.update({
            "allergies": allergies,
            "dislikes": dislikes,
            "religions": religions,
            "extra": {
                "allergy": request.POST.get("extra_allergy", "").strip(),
                "dislike": request.POST.get("extra_dislike", "").strip(),
                "religion": request.POST.get("extra_religion", "").strip(),
            }
        })
        request.session["plan"] = plan
        request.session.modified = True
        return redirect("plan:summary")

    return render(request, "plan/plan_diet.html", {
        "plan": plan,
        "allergy_choices": allergy_choices,
        "dislike_choices": dislike_choices,
        "religion_choices": religion_choices,
    })


@login_required
def mealplan_summary(request):
    """
    หน้าสรุปแผน:
    - budget ใน session = งบรวมทั้งช่วง (1 หรือ 7 วัน)
    - daily_budget = budget / days
    - ส่ง start_date + days ไปให้ JS ใช้สร้าง dropdown วันในแผนแบบชัวร์
    """
    plan = request.session.get("plan")
    if not plan:
        plan = _ensure_session_plan(request)

    days = _parse_int(plan.get("days", 7), 7)
    if days not in (1, 7):
        days = 7

    total_budget = _parse_int(plan.get("budget", 0), 0)
    daily_budget = _daily_budget(total_budget, days)

    start_date = _parse_date(plan.get("start_date"))
    end_inclusive = _plan_end_date(start_date, days)

    # สุ่มร้าน 3 ร้าน
    all_ids = list(Restaurant.objects.values_list("id", flat=True))
    picked_ids = random.sample(all_ids, min(3, len(all_ids))) if all_ids else []
    restaurants = Restaurant.objects.filter(id__in=picked_ids)

    data: List[Tuple[Restaurant, List[Menu]]] = []
    price_limit = daily_budget if daily_budget > 0 else None

    for r in restaurants:
        menus_qs = Menu.objects.filter(restaurant=r)
        menus_qs = filter_by_plan(menus_qs, plan)
        if price_limit:
            menus_qs = menus_qs.filter(price__lte=price_limit)
        data.append((r, list(menus_qs)))

    selected_menus = request.session.get("selected_menus", [])
    if not isinstance(selected_menus, list):
        selected_menus = []

    used_amount = 0.0
    for m in selected_menus:
        try:
            used_amount += float(m.get("price", 0) or 0)
        except Exception:
            pass

    remaining_budget = float(total_budget) - used_amount

    return render(request, "plan/summary.html", {
        "plan": plan,
        "restaurant_menus": data,
        "meal_choices": ["มื้อเช้า", "มื้อเที่ยง", "มื้อเย็น"],
        "today": timezone.localdate(),
        "selected_menus_json": json.dumps(selected_menus, ensure_ascii=False),

        "total_budget": total_budget,
        "daily_budget": daily_budget,
        "used_amount": round(used_amount, 2),
        "remaining_budget": round(remaining_budget, 2),

        "plan_start_date": start_date.isoformat(),
        "plan_days": days,
        "plan_end_date": end_inclusive.isoformat(),
    })


# ----------------- SAVE PLAN -----------------
@login_required
@require_POST
def save_plan(request):
    """
    บันทึกแผนมื้ออาหารจากหน้า summary
    - ล็อกตามงบเฉลี่ยต่อวัน (daily_budget)
    - ถ้าวันไหนเกิน daily_budget -> ไม่ให้บันทึกแผน
    - ✅ บันทึกเสร็จแล้ว Redirect ไปหน้า Dashboard (budgets:weekly_summary)
    """

    # 1) ดึงเมนูที่เลือก
    try:
        raw = json.loads(request.POST.get("menus", "[]"))
    except json.JSONDecodeError:
        raw = []

    menus = _normalize_selected_menus(raw)
    if not menus:
        messages.error(request, "กรุณาเลือกเมนูก่อนบันทึกแผน")
        return redirect("plan:summary")

    # 2) ดึงแผนจาก session
    sess = request.session.get("plan") or {}
    start_date = _parse_date(sess.get("start_date"))
    days = _parse_int(sess.get("days", 7), 7)
    if days not in (1, 7):
        days = 7

    total_budget = _parse_int(sess.get("budget", 0), 0)
    daily_budget = _daily_budget(total_budget, days)
    end_date_inclusive = _plan_end_date(start_date, days)

    # 3) VALIDATE: รวมเงินต่อวันห้ามเกิน daily_budget
    if daily_budget > 0:
        sums = {}  # {date_iso: float}
        for m in menus:
            menu = Menu.objects.filter(pk=m["id"]).first()
            if not menu:
                continue

            spend_date = _menu_date_from_payload(start_date, m)
            if spend_date < start_date:
                spend_date = start_date
            if spend_date > end_date_inclusive:
                spend_date = end_date_inclusive

            key = spend_date.isoformat()
            sums[key] = (sums.get(key, 0.0) + float(menu.price or 0))

        for d_iso, total in sums.items():
            if total > daily_budget:
                over = round(total - daily_budget, 2)
                messages.error(request, f"บันทึกแผนไม่ได้: วันที่ {d_iso} เกินงบเฉลี่ยต่อวัน {over} บาท")
                return redirect("plan:summary")

    # 4) ลบแผนเก่า (กันซ้ำ)
    old_plans = MealPlan.objects.filter(
        user=request.user,
        start_date=start_date,
        days=days,
    )

    if old_plans.exists():
        BudgetSpend.objects.filter(
            user=request.user,
            plan__in=old_plans,
            date__gte=start_date,
            date__lte=end_date_inclusive,
        ).delete()

        DailyBudget.objects.filter(
            user=request.user,
            plan__in=old_plans,
            date__gte=start_date,
            date__lte=end_date_inclusive,
        ).delete()

        old_plans.delete()

    # 5) สร้าง MealPlan
    plan_obj = MealPlan.objects.create(
        user=request.user,
        start_date=start_date,
        days=days,
        budget_per_day=daily_budget,
        title=sess.get("title", "") or "",
    )

    # 6) สร้าง DailyBudget ครบทุกวัน
    for i in range(days):
        d = start_date + timedelta(days=i)
        DailyBudget.objects.update_or_create(
            user=request.user,
            date=d,
            plan=plan_obj,
            defaults={"amount": daily_budget},
        )

    # 7) บันทึก BudgetSpend ตามวันจริง
    for m in menus:
        menu = Menu.objects.filter(pk=m["id"]).first()
        if not menu:
            continue

        spend_date = _menu_date_from_payload(start_date, m)
        if spend_date < start_date:
            spend_date = start_date
        if spend_date > end_date_inclusive:
            spend_date = end_date_inclusive

        BudgetSpend.objects.create(
            user=request.user,
            date=spend_date,
            amount=menu.price,
            menu=menu,
            plan=plan_obj,
            note=m["meal"],  # มื้อ
        )

    # 8) อัปเดต session
    sess["daily_budget"] = daily_budget
    request.session["plan"] = sess
    request.session["active_plan_id"] = plan_obj.id
    request.session["selected_menus"] = raw
    request.session.modified = True

    messages.success(request, "บันทึกแผนเรียบร้อยแล้ว")

    # กลับไป "ตารางรายวัน" ก่อน (ตามที่คุณต้องการ)
    url = reverse("budgets:home")
    return redirect(f"{url}?from_plan=1")


# ----------------- NEW: list plans -----------------
@login_required
def my_plans(request):
    active_id = request.session.get("active_plan_id")
    plans = MealPlan.objects.filter(user=request.user).order_by("-created_at")

    today = timezone.localdate()
    items = []

    for p in plans:
        start = p.start_date
        end_inclusive = _plan_end_date(p.start_date, p.days)
        items.append({
            "plan": p,
            "start": start,
            "end": end_inclusive,
            "is_active": (active_id == p.id),
            "in_range": (start <= today <= end_inclusive),
        })

    return render(request, "plan/my_plans.html", {"items": items})


@login_required
def use_plan(request, plan_id: int):
    plan = get_object_or_404(MealPlan, id=plan_id, user=request.user)
    request.session["active_plan_id"] = plan.id
    request.session.modified = True
    messages.success(request, f"ตั้งค่าใช้งานแผนเริ่ม {plan.start_date} แล้ว")
    return redirect("plan:my_plans")
