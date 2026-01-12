from __future__ import annotations

from datetime import timedelta, date
from typing import Optional

from django.db.models import Sum, Q, Count
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.views.decorators.http import require_POST

from .models import DailyBudget, BudgetSpend, MealPlan
from .forms import DailyBudgetForm
from menus.models import Menu
from recipes.models import Recipe


# ------------------ คีย์เวิร์ด/ข้อจำกัด ------------------
KW = {
    "หมู": ["หมู", "หมูกรอบ", "หมูสับ", "สามชั้น", "pork", "เบคอน", "bacon"],
    "ไก่": ["ไก่", "chicken"],
    "เนื้อวัว": ["เนื้อวัว", "เนื้อ", "วัว", "beef"],
    "กุ้ง": ["กุ้ง", "shrimp", "prawn"],
    "ทะเล": ["ทะเล", "ซีฟู้ด", "seafood", "หมึก", "ปลาหมึก", "squid", "หอย", "ปู", "crab", "clam", "oyster", "กุ้ง"],
    "เห็ด": ["เห็ด", "mushroom"],
    "หัวหอม": ["หัวหอม", "หอมใหญ่", "หอมแดง", "onion"],
    "เครื่องใน": ["เครื่องใน", "ตับ", "ไส้", "กึ๋น", "offal", "liver"],
    "ผักชี": ["ผักชี", "coriander", "cilantro"],
    "กระเทียม": ["กระเทียม", "garlic"],
    "นม": ["นม", "ชีส", "เนย", "milk", "cheese", "butter", "cream", "โยเกิร์ต", "yogurt"],
    "ไข่": ["ไข่", "egg"],
    "แป้งสาลี": ["แป้งสาลี", "แป้ง", "wheat", "กลูเตน", "gluten", "บะหมี่", "ขนมปัง", "แป้งทอด"],
    "ถั่ว": ["ถั่ว", "peanut", "อัลมอนด์", "almond", "nut"],
}

RELIGION_BLOCK = {
    "ฮาลาล": ["หมู", "pork", "เบคอน", "alcohol", "ไวน์", "เบียร์"],
    "อาหารเจ": ["หมู", "ไก่", "เนื้อวัว", "กุ้ง", "ทะเล", "ไข่", "นม", "meat", "egg", "milk", "butter"],
    "มังสวิรัติ": ["หมู", "ไก่", "เนื้อวัว", "กุ้ง", "ทะเล", "meat", "pork", "beef", "chicken", "seafood"],
    "หลีกเลี่ยงแอลกอฮอล์": ["alcohol", "ไวน์", "เบียร์", "rum", "whisky", "sake"],
}


def filter_by_plan(qs, plan: dict | None):
    """
    กรองเมนูตามแผน:
      - budget (ราคาไม่เกิน)
      - allergies + dislikes
      - religions
      - extra
    """
    if not plan:
        return qs

    budget = plan.get("budget")
    try:
        if budget is not None and str(budget).strip() != "":
            qs = qs.filter(price__lte=int(budget))
    except Exception:
        pass

    ban: list[str] = []
    allergies = plan.get("allergies") or []
    dislikes = plan.get("dislikes") or []

    for key in list(allergies) + list(dislikes):
        key = str(key).strip()
        if not key:
            continue
        ban += KW.get(key, [key])

    for r in plan.get("religions") or []:
        r = str(r).strip()
        if not r:
            continue
        ban += RELIGION_BLOCK.get(r, [])

    extra = plan.get("extra") or {}
    for e in (extra.get("allergy") or "").split(","):
        e = e.strip()
        if e:
            ban.append(e)
    for e in (extra.get("dislike") or "").split(","):
        e = e.strip()
        if e:
            ban.append(e)

    if ban:
        q_ex = Q()
        for w in set(ban):
            q_ex |= Q(name__icontains=w) | Q(description__icontains=w)
        qs = qs.exclude(q_ex)

    return qs.distinct()


# ----------------- helpers -----------------
MEAL_LABELS = ["มื้อเช้า", "มื้อเที่ยง", "มื้อเย็น"]


def _monday(d: date) -> date:
    return d - timedelta(days=d.weekday())


def _parse_date_or_today(date_str: str | None) -> date:
    if date_str:
        try:
            return date.fromisoformat(str(date_str))
        except Exception:
            return timezone.localdate()
    return timezone.localdate()


def _get_active_plan(request) -> Optional[MealPlan]:
    plan_id = request.session.get("active_plan_id")
    if not plan_id:
        return None
    return MealPlan.objects.filter(id=plan_id, user=request.user).first()


def _default_budget_from_session(request) -> int:
    sess_plan = request.session.get("plan") or {}
    try:
        return int(sess_plan.get("budget") or 0)
    except Exception:
        return 0


def _safe_get_or_create_daily(request, use_date: date, plan: Optional[MealPlan] = None):
    qs = DailyBudget.objects.filter(user=request.user, date=use_date, plan=plan).order_by("id")
    if qs.exists():
        return qs.first(), False

    return DailyBudget.objects.create(
        user=request.user,
        date=use_date,
        amount=_default_budget_from_session(request),
        plan=plan,
    ), True


def _meal_status_for_date(request, the_date: date, plan: Optional[MealPlan]):
    qs = BudgetSpend.objects.filter(
        user=request.user,
        date=the_date,
        note__in=MEAL_LABELS,
    )
    if plan:
        qs = qs.filter(plan=plan)

    done_set = set(qs.values_list("note", flat=True))
    done_labels = [x for x in MEAL_LABELS if x in done_set]
    missing_labels = [x for x in MEAL_LABELS if x not in done_set]

    return {
        "done_labels": done_labels,
        "missing_labels": missing_labels,
        "done_count": len(done_labels),
        "total": len(MEAL_LABELS),
        "is_complete": (len(done_labels) == len(MEAL_LABELS)),
    }


def _meal_badge(status: dict):
    done = status["done_count"]
    total = status["total"]

    if done == 0:
        return (f"ยังไม่เริ่ม {done}/{total}", "bg-gray-50 text-gray-700 ring-gray-200")
    if done < total:
        return (f"ค้าง {total - done}/{total}", "bg-yellow-50 text-yellow-800 ring-yellow-200")
    return (f"ครบ {done}/{total}", "bg-green-50 text-green-800 ring-green-200")


def _calc_match_score(total_budget: float, total_spent: float) -> int:
    if total_budget <= 0:
        return 0
    diff = abs(float(total_budget) - float(total_spent))
    score = 100 - int(round((diff / float(total_budget)) * 100))
    if score < 0:
        score = 0
    if score > 100:
        score = 100
    return score


# ----------------- ตารางงบ -----------------
@login_required
def budget_table(request):
    today = timezone.localdate()

    plan = _get_active_plan(request)
    plan_mode = bool(plan)

    if plan_mode:
        range_start = plan.start_date
        range_end = plan.start_date + timedelta(days=max(plan.days, 1) - 1)
    else:
        start_param = request.GET.get("start")
        try:
            start_date = date.fromisoformat(start_param) if start_param else today
        except Exception:
            start_date = today
        range_start = start_date
        range_end = start_date + timedelta(days=6)

    rows = []
    current = range_start
    total_budget = 0.0
    total_spent = 0.0

    while current <= range_end:
        budgets_qs = DailyBudget.objects.filter(user=request.user, date=current)
        spends_qs = BudgetSpend.objects.filter(user=request.user, date=current)

        if plan_mode:
            budgets_qs = budgets_qs.filter(plan=plan)
            spends_qs = spends_qs.filter(plan=plan)

        day_budget = budgets_qs.aggregate(total=Sum("amount"))["total"]

        # fallback: plan_mode แต่ยังไม่สร้าง DailyBudget
        if plan_mode and day_budget is None:
            day_budget = plan.budget_per_day or 0
        if day_budget is None:
            day_budget = 0

        day_spent = spends_qs.aggregate(total=Sum("amount"))["total"] or 0
        day_remain = float(day_budget) - float(day_spent)

        total_budget += float(day_budget)
        total_spent += float(day_spent)

        spends_list = list(spends_qs.select_related("menu"))

        meal_status = _meal_status_for_date(request, current, plan if plan_mode else None)
        badge_text, badge_class = _meal_badge(meal_status)

        rows.append({
            "date": current,
            "budget_amount": round(float(day_budget), 2),
            "spent_amount": round(float(day_spent), 2),
            "remain_amount": round(float(day_remain), 2),
            "spends": spends_list,
            "is_today": (current == today),

            "meal_status": meal_status,
            "meal_badge_text": badge_text,
            "meal_badge_class": badge_class,
        })

        current += timedelta(days=1)

    remaining = total_budget - total_spent
    num_days = (range_end - range_start).days + 1
    daily_average = round(total_budget / num_days, 2) if num_days > 0 else 0

    context = {
        "plan_mode": plan_mode,
        "plan": plan,
        "range_start": range_start,
        "range_end": range_end,
        "rows": rows,
        "today": today,
        "total_budget": round(total_budget, 2),
        "total_spent": round(total_spent, 2),
        "remaining": round(remaining, 2),
        "daily_average": daily_average,
    }

    if not plan_mode:
        context.update({
            "start_date": range_start,
            "prev_start": range_start - timedelta(days=7),
            "next_start": range_start + timedelta(days=7),
        })

    return render(request, "budgets/budget_table.html", context)


@login_required
def weekly_summary(request):
    """
    สรุป 7 วัน/ช่วงแผน:
    - อิง DailyBudget + BudgetSpend ตามช่วงวันเดียวกัน
    - จำนวนมื้อ นับจาก BudgetSpend.note (มื้อเช้า/เที่ยง/เย็น) เท่านั้น
    """
    today = timezone.localdate()

    plan = _get_active_plan(request)
    plan_mode = bool(plan)
    start_param = request.GET.get("start")

    if plan_mode:
        start_date = plan.start_date
        end_date = plan.start_date + timedelta(days=max(plan.days, 1) - 1)
    else:
        start_date = _parse_date_or_today(start_param)
        start_date = _monday(start_date)
        end_date = start_date + timedelta(days=6)

    budgets_qs = DailyBudget.objects.filter(
        user=request.user,
        date__range=[start_date, end_date],
    )
    spends_qs = BudgetSpend.objects.filter(
        user=request.user,
        date__range=[start_date, end_date],
    )

    if plan_mode:
        budgets_qs = budgets_qs.filter(plan=plan)
        spends_qs = spends_qs.filter(plan=plan)

    # map รายวัน
    spends_map = {
        row["date"]: float(row["total"] or 0)
        for row in spends_qs.values("date").annotate(total=Sum("amount"))
    }
    budgets_map = {
        row["date"]: float(row["total"] or 0)
        for row in budgets_qs.values("date").annotate(total=Sum("amount"))
    }

    # รวมทั้งช่วง
    total_budget = budgets_qs.aggregate(total=Sum("amount"))["total"]
    if plan_mode and total_budget is None:
        total_budget = (plan.budget_per_day or 0) * max(plan.days, 1)
    total_budget = float(total_budget or 0)

    total_spent = float(spends_qs.aggregate(total=Sum("amount"))["total"] or 0)
    remaining = total_budget - total_spent

    num_days = (end_date - start_date).days + 1
    daily_average = round(total_budget / num_days, 2) if num_days > 0 else 0

    over_amount = max(0.0, total_spent - total_budget)
    under_amount = max(0.0, total_budget - total_spent)

    # ตารางรายวัน
    rows = []
    cur = start_date
    while cur <= end_date:
        b = budgets_map.get(cur, None)
        if plan_mode and b is None:
            b = float(plan.budget_per_day or 0)
        b = float(b or 0)

        s = float(spends_map.get(cur, 0) or 0)
        remain_amount = b - s

        if b == 0 and s == 0:
            status = "none"
        elif b == 0 and s > 0:
            status = "no_budget"
        elif s > b:
            status = "over"
        elif s < b:
            status = "under"
        else:
            status = "equal"

        rows.append({
            "date": cur,
            "budget_amount": round(b, 2),
            "spent_amount": round(s, 2),
            "remain_amount": round(remain_amount, 2),
            "status": status,
            "is_today": cur == today,
        })
        cur += timedelta(days=1)

    # จำนวนมื้อ: นับจาก BudgetSpend.note เท่านั้น
    meal_spends_qs = spends_qs.filter(note__in=MEAL_LABELS)
    total_meals = meal_spends_qs.count()

    meal_counts = (
        meal_spends_qs.values("note")
        .annotate(total=Count("id"))
        .order_by("-total")
    )
    meals_by_type = [{"meal_type": r["note"], "label": r["note"], "total": r["total"]} for r in meal_counts]

    # เมนูแพงสุด/ถูกสุด (เฉพาะที่มี menu)
    menu_totals = (
        spends_qs.filter(menu__isnull=False)
        .values("menu_id", "menu__name")
        .annotate(total=Sum("amount"))
    )
    expensive_menus = [{"name": r["menu__name"], "total": float(r["total"] or 0)} for r in menu_totals.order_by("-total")[:3]]
    cheap_menus = [{"name": r["menu__name"], "total": float(r["total"] or 0)} for r in menu_totals.order_by("total")[:3]]

    match_score = _calc_match_score(total_budget, total_spent)

    prev_start = next_start = None
    if not plan_mode:
        prev_start = start_date - timedelta(days=7)
        next_start = start_date + timedelta(days=7)

    context = {
        "plan_mode": plan_mode,
        "plan": plan,
        "start_date": start_date,
        "end_date": end_date,
        "rows": rows,

        "total_budget": round(total_budget, 2),
        "daily_average": daily_average,
        "total_spent": round(total_spent, 2),
        "remaining": round(remaining, 2),
        "over_amount": round(over_amount, 2),
        "under_amount": round(under_amount, 2),

        "total_meals": total_meals,
        "meals_by_type": meals_by_type,
        "expensive_menus": expensive_menus,
        "cheap_menus": cheap_menus,
        "match_score": match_score,

        "prev_start": prev_start,
        "next_start": next_start,
    }
    return render(request, "budgets/weekly_summary.html", context)


@login_required
def set_daily_budget(request, date_str=None):
    initial_date = _parse_date_or_today(date_str) if date_str else None
    active_plan = _get_active_plan(request) if request.GET.get("from_plan") == "1" else None

    if request.method == "POST":
        form = DailyBudgetForm(request.POST)
        if form.is_valid():
            d = form.cleaned_data["date"]
            amt = form.cleaned_data["amount"]
            obj, _ = _safe_get_or_create_daily(request, d, plan=active_plan)
            obj.amount = amt
            obj.save(update_fields=["amount"])
            messages.success(request, f"บันทึกงบ {d} = {amt} บาท")
            if request.GET.get("from_plan") == "1":
                return redirect("/budget/?from_plan=1")
            return redirect(f"/budget/?start={_monday(d).isoformat()}")
    else:
        initial = {}
        if initial_date:
            initial["date"] = initial_date
            exist_qs = DailyBudget.objects.filter(user=request.user, date=initial_date)
            if active_plan:
                exist_qs = exist_qs.filter(plan=active_plan)
            exist = exist_qs.order_by("id").first()
            if exist:
                initial["amount"] = exist.amount
        form = DailyBudgetForm(initial=initial)

    return render(request, "budgets/set_daily_budget.html", {"form": form})


@login_required
@require_POST
def consume_menu(request, menu_id: int):
    menu = get_object_or_404(Menu, pk=menu_id)
    use_date = _parse_date_or_today(request.POST.get("date"))

    active_plan = _get_active_plan(request)
    _safe_get_or_create_daily(request, use_date, plan=active_plan)

    note = (request.POST.get("meal_label") or "").strip()
    if not note:
        note = f"กินเมนู {menu.name}"

    BudgetSpend.objects.create(
        user=request.user,
        date=use_date,
        amount=menu.price,
        menu=menu,
        plan=active_plan,   # ผูกกับแผน active
        note=note,
    )
    messages.success(request, f"บันทึก {menu.name} {menu.price} บาท (วันที่ {use_date})")
    return redirect("/budget/?from_plan=1")


@login_required
@require_POST
def consume_outside(request):
    try:
        amount = int(request.POST.get("amount", "0") or 0)
    except Exception:
        amount = 0

    if amount <= 0:
        messages.error(request, "กรุณาระบุจำนวนเงินให้ถูกต้อง")
        next_url = request.GET.get("next") or "/budget/"
        return redirect(next_url)

    note = (request.POST.get("note") or "").strip()
    use_date = _parse_date_or_today(request.POST.get("date"))

    active_plan = _get_active_plan(request)
    _safe_get_or_create_daily(request, use_date, plan=active_plan)

    BudgetSpend.objects.create(
        user=request.user,
        date=use_date,
        amount=amount,
        plan=active_plan,   # ผูกกับแผน active
        note=note or "รายการอื่น ๆ",
    )
    messages.success(request, f"บันทึกการใช้จ่าย {amount} บาท (วันที่ {use_date})")

    next_url = request.GET.get("next") or "/budget/?from_plan=1"
    return redirect(next_url)


def _tokens_from_menu_name(name: str) -> list[str]:
    if not name:
        return []

    s = str(name).strip()

    CORE_KEYWORDS = [
        "กะเพรา", "กระเพรา",
        "ผัด", "แกง", "ต้ม", "ทอด", "ยำ", "นึ่ง", "อบ",
        "ข้าวผัด", "ข้าวหน้า", "ราดหน้า", "ผัดไทย",
        "ก๋วยเตี๋ยว", "ขนมจีน", "ส้มตำ", "ลาบ", "น้ำตก",
        "ต้มยำ", "แกงจืด", "พะโล้", "ผัดพริก", "ผัดพริกแกง",
    ]

    tokens = [kw for kw in CORE_KEYWORDS if kw in s]
    if not tokens:
        tokens = [s[:3]] if len(s) >= 3 else [s]

    return tokens[:5]


@login_required
def day_detail(request, date_str):
    the_date = _parse_date_or_today(date_str)
    active_plan = _get_active_plan(request)

    budget_obj_qs = DailyBudget.objects.filter(user=request.user, date=the_date)
    if active_plan:
        budget_obj_qs = budget_obj_qs.filter(plan=active_plan)
    budget_obj = budget_obj_qs.order_by("id").first()

    if budget_obj:
        budget_amount = float(budget_obj.amount or 0)
        current_plan = budget_obj.plan
    else:
        if active_plan:
            budget_amount = float(active_plan.budget_per_day or 0)
            current_plan = active_plan
        else:
            budget_amount = 0.0
            current_plan = None

    spends_qs = BudgetSpend.objects.filter(user=request.user, date=the_date).select_related("menu").order_by("created_at")
    if current_plan:
        spends_qs = spends_qs.filter(plan=current_plan)

    plan_spends = list(spends_qs)
    spent_sum = float(spends_qs.aggregate(total=Sum("amount"))["total"] or 0)
    remain = budget_amount - spent_sum

    grouped = {label: [] for label in MEAL_LABELS}
    other_spends = []

    for s in plan_spends:
        if s.note in MEAL_LABELS:
            grouped[s.note].append(s)
        else:
            other_spends.append(s)

    meal_groups = [{"label": label, "items": grouped[label]} for label in MEAL_LABELS]

    suggested_recipes = []
    seen_recipe_ids = set()

    menu_names = []
    for s in plan_spends:
        if s.menu and s.menu.name:
            menu_names.append(s.menu.name.strip())

    for name in menu_names:
        tokens = _tokens_from_menu_name(name)
        if not tokens:
            continue

        q = Q()
        for t in tokens:
            q |= Q(title__icontains=t) | Q(description__icontains=t)

        qs = Recipe.objects.filter(q).order_by("-created_at")[:6]
        for r in qs:
            if r.id not in seen_recipe_ids:
                seen_recipe_ids.add(r.id)
                suggested_recipes.append(r)

        if len(suggested_recipes) >= 8:
            break

    context = {
        "date": the_date,
        "budget_amount": round(budget_amount, 2),
        "spent_sum": round(spent_sum, 2),
        "remain": round(remain, 2),
        "meal_groups": meal_groups,
        "other_spends": other_spends,
        "suggested_recipes": suggested_recipes,
        "week_start": the_date - timedelta(days=the_date.weekday()),
        "plan_mode": bool(active_plan),
        "plan": active_plan,
    }
    return render(request, "budgets/day_detail.html", context)


@login_required
@require_POST
def delete_spend(request, pk):
    obj = get_object_or_404(BudgetSpend, pk=pk, user=request.user)
    d = obj.date
    obj.delete()
    messages.success(request, "ลบรายการเรียบร้อยแล้ว")
    if request.GET.get("from_plan") == "1":
        return redirect("/budget/?from_plan=1")
    return redirect("budgets:day_detail", date_str=d.isoformat())


@login_required
@require_POST
def set_week_same_amount(request):
    try:
        amount = int(request.POST.get("amount", "0") or 0)
    except Exception:
        amount = 0

    start_str = request.POST.get("start")
    if amount <= 0 or not start_str:
        messages.error(request, "กรุณากรอกจำนวนเงินและสัปดาห์ให้ถูกต้อง")
        return redirect("/budget/")

    start_date = _parse_date_or_today(start_str)
    active_plan = _get_active_plan(request) if request.GET.get("from_plan") == "1" else None

    for i in range(7):
        d = start_date + timedelta(days=i)
        obj, _ = _safe_get_or_create_daily(request, d, plan=active_plan)
        obj.amount = amount
        obj.save(update_fields=["amount"])

    messages.success(request, f"ตั้งงบ {amount} บาท/วัน สำหรับสัปดาห์ที่เริ่ม {start_date} เรียบร้อย")
    if request.GET.get("from_plan") == "1":
        return redirect("/budget/?from_plan=1")
    return redirect(f"/budget/?start={start_date.isoformat()}")


@require_POST
def save_expense(request):
    return consume_outside(request)


@require_POST
def save_menu_expense(request, menu_id: int):
    return consume_menu(request, menu_id)
