from __future__ import annotations

import json
import random
from datetime import date, timedelta
from typing import List, Tuple, Dict, Any

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Sum
from django.shortcuts import redirect, render, get_object_or_404
from django.urls import reverse
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


def _parse_float(v, default: float) -> float:
    try:
        return float(v)
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
    if not start:
        start = timezone.localdate()
    if not days or days <= 0:
        days = 1
    return start + timedelta(days=days - 1)


def _daily_budget(total_budget: float, days: int) -> float:
    if not days or days <= 0:
        days = 1
    if not total_budget or total_budget <= 0:
        return 0.0
    return round(float(total_budget) / float(days), 2)


def _menu_date_from_payload(start_date: date, payload: dict) -> date:
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


def _ensure_session_plan(request) -> Dict[str, Any]:
    if "plan" not in request.session or not isinstance(request.session.get("plan"), dict):
        request.session["plan"] = {
            "days": 7,
            "budget": 350.0,  # งบรวมทั้งช่วง
            "start_date": timezone.localdate().isoformat(),
            "allergies": [],
            "dislikes": [],
            "religions": [],
            "extra": {},
            "title": "",
        }
        request.session.modified = True
    return request.session["plan"]


def _normalize_selected_menus(menus):
    if not isinstance(menus, list):
        return []

    out = []
    for m in menus:
        if not isinstance(m, dict):
            continue

        try:
            menu_id = int(m.get("id"))
        except Exception:
            continue

        meal = (m.get("meal") or "").strip()
        if not meal:
            continue

        d = m.get("date")
        day_offset = m.get("day_offset")
        if day_offset is not None:
            try:
                day_offset = int(day_offset)
            except Exception:
                day_offset = None

        key = (m.get("key") or "").strip()

        out.append({
            "id": menu_id,
            "meal": meal,
            "date": str(d) if d else "",
            "day_offset": day_offset,
            "key": key,
        })

    return out


def _pick_best_date_for_plan(plan: MealPlan, today: date) -> date:
    """
    เลือกวันที่จะพาไปหน้า day_detail จากหน้า my-plans:
    - ถ้าวันนี้อยู่ในช่วงแผน -> ใช้วันนี้
    - ถ้ายังไม่ถึง -> ใช้วันเริ่มแผน
    - ถ้าจบแล้ว -> ใช้วันสุดท้ายของแผน
    """
    start = plan.start_date
    end_ = _plan_end_date(plan.start_date, plan.days)

    if today < start:
        return start
    if today > end_:
        return end_
    return today

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

        budget = _parse_float(request.POST.get("budget", "350"), 350.0)
        start_date = _parse_date(request.POST.get("start_date", ""))

        old = request.session.get("plan", {}) or {}
        request.session["plan"] = {
            "days": days,
            "budget": float(budget),
            "start_date": start_date.isoformat(),
            "allergies": old.get("allergies", []),
            "dislikes": old.get("dislikes", []),
            "religions": old.get("religions", []),
            "extra": old.get("extra", {}),
            "title": old.get("title", "") or "",
        }

        request.session.pop("selected_menus", None)
        request.session.pop("active_plan_id", None)
        request.session.modified = True
        return redirect("plan:diet")

    request.session.pop("selected_menus", None)
    request.session.pop("active_plan_id", None)
    request.session.modified = True
    return redirect("plan:diet")


@login_required
def plan_diet(request):
    plan = _ensure_session_plan(request)

    allergy_choices = ["กุ้ง", "นม", "แป้งสาลี", "ไข่", "ถั่ว", "ทะเล"]
    dislike_choices = ["หมู", "ไก่", "เห็ด", "หัวหอม", "เครื่องใน", "ผักชี", "กระเทียม", "เนื้อวัว"]
    religion_choices = ["ฮาลาล", "มังสวิรัติ", "อาหารเจ", "หลีกเลี่ยงแอลกอฮอล์"]

    if request.method == "POST":
        allergies = request.POST.getlist("allergies")
        dislikes = request.POST.getlist("dislikes")
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
    Summary:
    - ถ้ามี plan_id ใน query -> ใช้แผนจาก DB
    - ถ้าไม่มี -> ใช้ active_plan_id ใน session
    - ถ้าไม่มีอีก -> ใช้ session plan (กรณีสร้างแผนใหม่)
    """
    # 1) หา plan_id จาก URL หรือจาก active ใน session
    plan_id = request.GET.get("plan_id") or request.session.get("active_plan_id")

    plan_obj = None
    if plan_id:
        try:
            plan_id_int = int(plan_id)
            plan_obj = MealPlan.objects.filter(id=plan_id_int, user=request.user).first()
        except Exception:
            plan_obj = None

    # 2) สร้าง plan dict ที่ใช้กับ filter_by_plan ให้เป็น format เดิม
    if plan_obj:
        # ✅ ใช้แผนจริงในฐานข้อมูล
        days = int(plan_obj.days or 1)
        total_budget = float(plan_obj.budget_per_day or 0) * float(days)
        daily_budget = float(plan_obj.budget_per_day or 0)
        start_date = plan_obj.start_date
        plan = {
            "days": days,
            "budget": total_budget,                     # งบรวมทั้งช่วง (เหมือน session)
            "start_date": start_date.isoformat(),
            "allergies": [],
            "dislikes": [],
            "religions": [],
            "extra": {},
            "title": plan_obj.title or "",
        }
        end_inclusive = _plan_end_date(start_date, days)

        # ใช้ยอดใช้จริงจาก BudgetSpend ของแผนนี้ (แม่นสุด)
        used_amount = (
            BudgetSpend.objects.filter(user=request.user, plan=plan_obj)
            .aggregate(s=Sum("amount"))["s"] or 0
        )
        used_amount = float(used_amount)
        remaining_budget = float(total_budget) - used_amount

    else:
        # ✅ fallback: กรณีสร้างแผนใหม่ ยังไม่ save (ใช้ session เหมือนเดิม)
        plan = request.session.get("plan") or _ensure_session_plan(request)

        days = _parse_int(plan.get("days", 7), 7)
        if days not in (1, 7):
            days = 7

        total_budget = _parse_float(plan.get("budget", 0), 0.0)
        daily_budget = _daily_budget(total_budget, days)

        start_date = _parse_date(plan.get("start_date"))
        end_inclusive = _plan_end_date(start_date, days)

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

    # 3) แนะนำร้าน/เมนู (เหมือนเดิม)
    all_ids = list(Restaurant.objects.values_list("id", flat=True))
    picked_ids = random.sample(all_ids, min(3, len(all_ids))) if all_ids else []
    restaurants = Restaurant.objects.filter(id__in=picked_ids)

    data: List[Tuple[Restaurant, List[Menu]]] = []
    price_limit = daily_budget if daily_budget > 0 else None

    for r in restaurants:
        # NOTE: ของคุณใช้ FK restaurant ใน Menu อยู่แล้ว
        menus_qs = Menu.objects.filter(restaurant=r)
        menus_qs = filter_by_plan(menus_qs, plan)
        if price_limit:
            menus_qs = menus_qs.filter(price__lte=price_limit)
        data.append((r, list(menus_qs)))

    # 4) selected_menus_json (ถ้าเป็นแผนจาก DB อาจไม่ต้องใช้ แต่ให้ไม่พัง)
    selected_menus = request.session.get("selected_menus", [])
    if not isinstance(selected_menus, list):
        selected_menus = []

    return render(request, "plan/summary.html", {
        "plan": plan,
        "restaurant_menus": data,
        "meal_choices": ["มื้อเช้า", "มื้อเที่ยง", "มื้อเย็น"],
        "today": timezone.localdate(),
        "selected_menus_json": json.dumps(selected_menus, ensure_ascii=False),

        "total_budget": round(float(total_budget), 2),
        "daily_budget": round(float(daily_budget), 2),
        "used_amount": round(float(used_amount), 2),
        "remaining_budget": round(float(remaining_budget), 2),

        "plan_start_date": start_date.isoformat(),
        "plan_days": int(days),
        "plan_end_date": end_inclusive.isoformat(),

        # ส่ง plan_id ให้ template ถ้าต้องใช้ลิงก์ต่อ
        "active_plan_id": plan_obj.id if plan_obj else None,
    })


@login_required
@require_POST
def save_plan(request):
    # ✅ โหมดคุมเข้ม: True = เกินงบ/วัน ห้ามบันทึก, False = เตือนแต่ยังบันทึก
    STRICT_PER_DAY = False

    try:
        raw = json.loads(request.POST.get("menus", "[]"))
    except Exception:
        raw = []

    menus = _normalize_selected_menus(raw)
    if not menus:
        messages.error(request, "กรุณาเลือกเมนูก่อนบันทึกแผน")
        return redirect("plan:summary")

    sess = request.session.get("plan") or _ensure_session_plan(request)
    start_date = _parse_date(sess.get("start_date"))
    days = _parse_int(sess.get("days", 7), 7)
    if days not in (1, 7):
        days = 7

    total_budget = _parse_float(sess.get("budget", 0), 0.0)
    daily_budget = _daily_budget(total_budget, days)
    end_date_inclusive = _plan_end_date(start_date, days)

    # -------------------------------
    # helper: หา date ให้เมนูแบบปลอดภัย
    # ถ้ามี date/day_offset ใช้ตามนั้น
    # ถ้าไม่มี -> กระจายตาม index ไปแต่ละวัน (กันกองวันเดียว)
    # -------------------------------
    def _safe_plan_date(start_date: date, payload: dict, idx: int) -> date:
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

        # ✅ fallback สำคัญ: กระจายวันตามลำดับเมนู
        off = idx % max(int(days), 1)
        return start_date + timedelta(days=off)

    # -------------------------------
    # validate per-day
    # -------------------------------
    if daily_budget > 0:
        sums: Dict[str, float] = {}
        for idx, m in enumerate(menus):
            menu = Menu.objects.filter(pk=m["id"]).only("id", "price").first()
            if not menu:
                continue

            spend_date = _safe_plan_date(start_date, m, idx)
            spend_date = max(start_date, min(end_date_inclusive, spend_date))
            k = spend_date.isoformat()
            sums[k] = sums.get(k, 0.0) + float(menu.price or 0)

        overs = []
        for d_iso, total in sums.items():
            if total > daily_budget:
                over = round(total - daily_budget, 2)
                overs.append((d_iso, over))

        if overs:
            if STRICT_PER_DAY:
                d_iso, over = overs[0]
                messages.error(request, f"บันทึกแผนไม่ได้: วันที่ {d_iso} เกินงบเฉลี่ยต่อวัน {over} บาท")
                return redirect("plan:summary")
            else:
                msg = ", ".join([f"{d} เกิน {o} บาท" for d, o in overs])
                messages.warning(request, f"แจ้งเตือน: บางวันเกินงบเฉลี่ยต่อวัน ({msg}) แต่ระบบยังบันทึกแผนให้")

    # -------------------------------
    # กันซ้ำ: ลบแผนเดิมช่วงเดียวกัน
    # -------------------------------
    old_plans = MealPlan.objects.filter(user=request.user, start_date=start_date, days=days)
    if old_plans.exists():
        BudgetSpend.objects.filter(user=request.user, plan__in=old_plans).delete()
        DailyBudget.objects.filter(user=request.user, plan__in=old_plans).delete()
        old_plans.delete()

    # -------------------------------
    # create plan
    # -------------------------------
    plan_obj = MealPlan.objects.create(
        user=request.user,
        start_date=start_date,
        days=days,
        budget_per_day=daily_budget,
        title=(sess.get("title", "") or ""),
    )

    # DailyBudget
    for i in range(days):
        d = start_date + timedelta(days=i)
        DailyBudget.objects.update_or_create(
            user=request.user,
            date=d,
            plan=plan_obj,
            defaults={"amount": daily_budget},
        )

    # BudgetSpend
    for idx, m in enumerate(menus):
        menu = Menu.objects.filter(pk=m["id"]).only("id", "price").first()
        if not menu:
            continue

        spend_date = _safe_plan_date(start_date, m, idx)
        spend_date = max(start_date, min(end_date_inclusive, spend_date))

        BudgetSpend.objects.create(
            user=request.user,
            date=spend_date,
            amount=float(menu.price or 0),
            menu=menu,
            plan=plan_obj,
            note=m["meal"],
        )

    # session
    request.session["active_plan_id"] = plan_obj.id
    request.session["selected_menus"] = raw
    request.session.modified = True

    messages.success(request, "บันทึกแผนเรียบร้อยแล้ว")

    # ✅ เด้งไปหน้าตารางจากแผนตามรูป
    url = reverse("budgets:home")
    return redirect(f"{url}?from_plan=1&plan_id={plan_obj.id}")


@login_required
def my_plans(request):
    active_id = request.session.get("active_plan_id")
    plans = MealPlan.objects.filter(user=request.user).order_by("-created_at")

    today = timezone.localdate()
    items: List[Dict[str, Any]] = []

    for p in plans:
        start = p.start_date
        end_inclusive = _plan_end_date(p.start_date, p.days)

        # งบรวมของแผน
        days = int(p.days or 1)
        daily = float(p.budget_per_day or 0)
        total_budget = daily * days

        # ใช้ไปแล้วในช่วงแผน
        spent = (
            BudgetSpend.objects.filter(
                user=request.user,
                plan=p,
                date__gte=start,
                date__lte=end_inclusive,
            ).aggregate(s=Sum("amount"))["s"]
            or 0
        )
        spent = float(spent)
        remaining = total_budget - spent

        # สถานะ
        is_active = (active_id == p.id)
        if is_active:
            status_key = "active"
        elif today < start:
            status_key = "upcoming"
        elif today > end_inclusive:
            status_key = "ended"
        else:
            status_key = "in_range"

        # วันที่ที่ควรพาไปดูรายละเอียด (day_detail)
        best_date = _pick_best_date_for_plan(p, today)

        # URL ไปหน้า day_detail แบบในรูป (ล็อก plan_id + from_plan=1)
        day_detail_url = reverse("budgets:day_detail", kwargs={"date_str": best_date.isoformat()})
        day_detail_url = f"{day_detail_url}?from_plan=1&plan_id={p.id}"

        # URL dashboard ของแผน (ถ้าคุณยังอยากมี)
        dashboard_url = reverse("budgets:dashboard") + f"?plan_id={p.id}"

        items.append({
            "plan": p,
            "start": start,
            "end": end_inclusive,
            "days": days,

            "total_budget": round(total_budget, 2),
            "spent": round(spent, 2),
            "remaining": round(remaining, 2),

            "is_active": is_active,
            "status_key": status_key,

            "best_date": best_date,
            "day_detail_url": day_detail_url,
            "dashboard_url": dashboard_url,
        })

    return render(request, "plan/my_plans.html", {"items": items})


@login_required
def use_plan(request, plan_id: int):
    """
    ใช้แผนนี้ = ตั้ง active และ sync session["plan"] ให้ตรงกับแผนใน DB
    เพื่อให้หน้า Summary/ตารางงบ ใช้ค่า budget/day ถูกต้อง
    """
    plan = get_object_or_404(MealPlan, id=plan_id, user=request.user)

    # ✅ ตั้ง active
    request.session["active_plan_id"] = plan.id

    # ✅ sync session plan ให้ตรงกับแผนที่เลือกจริง
    days = int(plan.days or 1)
    daily = float(plan.budget_per_day or 0)
    total_budget = daily * days

    request.session["plan"] = {
        "days": days,
        "budget": float(total_budget),               # งบรวมทั้งช่วง
        "start_date": plan.start_date.isoformat(),
        "allergies": [],
        "dislikes": [],
        "religions": [],
        "extra": {},
        "title": plan.title or "",
    }

    # ✅ เคลียร์ selected_menus ของแผนกำลังสร้าง (กันเอาของเก่ามาปน)
    request.session.pop("selected_menus", None)
    request.session.modified = True

    messages.success(request, "ตั้งค่าแผนที่กำลังใช้งานเรียบร้อยแล้ว")
    return redirect("plan:my_plans")
