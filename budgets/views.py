# budgets/views.py
from datetime import timedelta, date

from django.db.models import Sum, Q
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.views.decorators.http import require_POST

from .models import DailyBudget, BudgetSpend, MealPlan, MealItem
from .forms import DailyBudgetForm
from menus.models import Menu
from recipes.models import Recipe  # ใช้สำหรับสูตรอาหารแนะนำ


# ----------------- helpers -----------------
def _monday(d: date):
    return d - timedelta(days=d.weekday())


def _parse_date_or_today(date_str: str | None):
    """รับ YYYY-MM-DD -> date; ถ้า None/ว่าง ใช้วันนี้"""
    if date_str:
        return timezone.datetime.fromisoformat(date_str).date()
    return timezone.localdate()


def _default_budget_from_session(request) -> int:
    """ดึงงบ default จากแผนใน session (ถ้ามี)"""
    plan = request.session.get('plan') or {}
    try:
        return int(plan.get('budget') or 0)
    except Exception:
        return 0


def _safe_get_or_create_daily(
    request,
    use_date: date,
    plan: MealPlan | None = None
):
    """
    ดึง/สร้าง DailyBudget ของ user+date+plan แบบปลอดภัย:
    - ถ้ามีหลายแถว (ข้อมูลซ้ำ) จะเลือก id ต่ำสุดมาใช้
    - ถ้าไม่มี -> สร้างใหม่ด้วยงบ default จาก session
    """
    qs = DailyBudget.objects.filter(
        user=request.user,
        date=use_date,
        plan=plan
    ).order_by("id")

    if qs.exists():
        return qs.first(), False

    return DailyBudget.objects.create(
        user=request.user,
        date=use_date,
        amount=_default_budget_from_session(request),
        plan=plan,
    ), True


def _plan_range(request):
    """
    คืน (start_date, end_date, plan_obj) จาก session['plan']
    ถ้าไม่มี/รูปแบบไม่ถูก -> คืน (None, None, None)
    จะพยายามใช้ active_plan_id ก่อน ถ้าไม่มีค่อย fallback เป็นแผนล่าสุดของ user
    """
    plan = request.session.get("plan")
    if not plan:
        return (None, None, None)

    start_str = plan.get("start_date") or ""
    days = plan.get("days") or 1

    try:
        s = date.fromisoformat(start_str) if start_str else timezone.localdate()
    except Exception:
        s = timezone.localdate()

    try:
        days = int(days)
    except Exception:
        days = 1

    e = s + timedelta(days=days - 1)

    plan_obj = None
    active_id = request.session.get("active_plan_id")
    if active_id:
        plan_obj = MealPlan.objects.filter(
            user=request.user,
            id=active_id,
        ).first()

    if not plan_obj:
        plan_obj = MealPlan.objects.filter(
            user=request.user
        ).order_by("-created_at").first()

    return (s, e, plan_obj)


# ----------------- ตารางงบ -----------------
DESSERT_THRESHOLD = 20  # กันสำรองอย่างน้อย 20 บาท


@login_required
def budget_table(request):
    """
    โหมดปกติ (รายสัปดาห์): /budget/?start=YYYY-MM-DD
    โหมดแผน:               /budget/?from_plan=1  -> แสดงเฉพาะช่วงใน session['plan']
    """
    plan_mode = (request.GET.get('from_plan') == '1')

    if plan_mode:
        range_start, range_end, plan_obj = _plan_range(request)
        if not range_start:
            messages.info(request, "ยังไม่มีช่วงแผนในเซสชัน กรุณาเริ่มวางแผนก่อน")
            return redirect("/accounts/home/")

        start_date = range_start
        end_date = range_end

        budgets_qs = DailyBudget.objects.filter(
            user=request.user,
            date__range=[range_start, range_end],
            plan=plan_obj,
        ).order_by('date')

        # เมนูในแผน (MealItem) ของ user นี้ในช่วงแผน
        plan_meals_qs = (
            MealItem.objects.filter(
                user=request.user,
                plan=plan_obj,
                date__range=[range_start, range_end],
            )
            .select_related('menu')
            .order_by('date', 'meal_type')
        )

    else:
        start_date = _parse_date_or_today(request.GET.get('start'))
        start_date = _monday(start_date)
        end_date = start_date + timedelta(days=6)

        budgets_qs = DailyBudget.objects.filter(
            user=request.user,
            date__range=[start_date, end_date],
        ).order_by('date')

        # โหมดปกติ: ดึง MealItem ตามช่วงสัปดาห์ (ไม่ fix plan)
        plan_meals_qs = (
            MealItem.objects.filter(
                user=request.user,
                date__range=[start_date, end_date],
            )
            .select_related('menu', 'plan')
            .order_by('date', 'meal_type')
        )

    # map {date: [MealItem, ...]}
    meals_by_date: dict[date, list[MealItem]] = {}
    for mi in plan_meals_qs:
        meals_by_date.setdefault(mi.date, []).append(mi)

    # รวมยอดใช้จ่ายจริงต่อวัน
    planned_dates = [b.date for b in budgets_qs]

    if plan_mode:
        spends_qs = BudgetSpend.objects.filter(
            user=request.user,
            date__in=planned_dates,
            plan=plan_obj,
        )
    else:
        spends_qs = BudgetSpend.objects.filter(
            user=request.user,
            date__in=planned_dates,
        )

    spends_sum = spends_qs.values('date').annotate(total=Sum('amount'))
    spends_map = {row['date']: row['total'] or 0 for row in spends_sum}

    today = timezone.localdate()
    rows = []
    today_row = None

    for b in budgets_qs:
        spent = spends_map.get(b.date, 0)

        day_spends = (
            BudgetSpend.objects.filter(
                user=request.user,
                date=b.date,
                plan=b.plan if plan_mode else None,
            )
            .select_related('menu')
            .order_by('-created_at')
        )

        remain = b.amount - spent

        advice = ""
        over = False
        if remain < 0:
            over = True
            advice = f"ใช้เกินงบ {abs(remain)} บาท"
        elif remain > DESSERT_THRESHOLD:
            dessert_budget = remain - DESSERT_THRESHOLD
            advice = (
                f"งบเหลือ {remain} บาท • "
                f"ซื้อของหวานได้ไม่เกิน {dessert_budget} บาท "
                f"(กันสำรอง {DESSERT_THRESHOLD} บาท)"
            )
        elif remain > 0:
            advice = f"งบเหลือ {remain} บาท"

        row = {
            'date': b.date,
            'budget_amount': b.amount,
            'spent_amount': spent,
            'remain_amount': remain,
            'spends': day_spends,
            'meals': meals_by_date.get(b.date, []),
            'advice': advice,
            'over': over,
            'is_today': (b.date == today),
        }
        rows.append(row)
        if row['is_today']:
            today_row = row

    return render(request, 'budgets/budget_table.html', {
        'rows': rows,
        'start_date': start_date,
        'end_date': end_date,
        'prev_start': start_date - timedelta(days=7),
        'next_start': start_date + timedelta(days=7),
        'plan_mode': plan_mode,
        'range_start': start_date if plan_mode else None,
        'range_end': end_date if plan_mode else None,
        'restrict': False,  # ใช้ใน template เดิม
    })


# ----------------- ตั้ง/แก้งบรายวัน -----------------
@login_required
def set_daily_budget(request, date_str=None):
    initial_date = _parse_date_or_today(date_str) if date_str else None

    if request.method == "POST":
        form = DailyBudgetForm(request.POST)
        if form.is_valid():
            d = form.cleaned_data["date"]
            amt = form.cleaned_data["amount"]
            obj, _ = _safe_get_or_create_daily(request, d)
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
            exist = (
                DailyBudget.objects.filter(
                    user=request.user,
                    date=initial_date,
                )
                .order_by("id")
                .first()
            )
            if exist:
                initial["amount"] = exist.amount
        form = DailyBudgetForm(initial=initial)

    return render(request, "budgets/set_daily_budget.html", {"form": form})


# ----------------- บันทึกค่าใช้จ่าย -----------------
@login_required
@require_POST
def consume_menu(request, menu_id: int):
    menu = get_object_or_404(Menu, pk=menu_id)
    use_date = _parse_date_or_today(request.POST.get("date"))

    daily, _ = _safe_get_or_create_daily(request, use_date)

    BudgetSpend.objects.create(
        user=request.user,
        date=use_date,
        amount=menu.price,
        menu=menu,
        plan=daily.plan,
        note=f"กินเมนู {menu.name}",
    )
    messages.success(
        request,
        f"บันทึก {menu.name} {menu.price} บาท (วันที่ {use_date})",
    )
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
        return redirect("/budget/")

    note = (request.POST.get("note") or "").strip()
    use_date = _parse_date_or_today(request.POST.get("date"))

    daily, _ = _safe_get_or_create_daily(request, use_date)

    BudgetSpend.objects.create(
        user=request.user,
        date=use_date,
        amount=amount,
        plan=daily.plan,
        note=note or "กินข้างนอก",
    )
    messages.success(
        request,
        f"บันทึกการใช้จ่าย {amount} บาท (วันที่ {use_date})",
    )
    return redirect("/budget/?from_plan=1")


# ----------------- รายละเอียดรายวัน + สูตรอาหารแนะนำ -----------------
@login_required
def day_detail(request, date_str):
    """
    แสดงรายละเอียดงบของวันที่เลือก:
    - แสดงงบ/ใช้ไป/คงเหลือ ของวันนั้น
    - แสดงเมนูที่อยู่ใน 'แผน' ของวันนั้น แยกตามมื้อ (เช้า/เที่ยง/เย็น)
    - แสดงรายการใช้จ่ายอื่น ๆ (ที่ note ไม่ใช่มื้อ)
    - แนะนำสูตรอาหารจากชื่อเมนูในแผน
    """
    # แปลงวันที่จาก url (YYYY-MM-DD) ถ้า format ไม่ถูกจะ fallback เป็นวันนี้
    try:
        the_date = timezone.datetime.fromisoformat(date_str).date()
    except Exception:
        the_date = timezone.localdate()

    # ----------------- ดึง DailyBudget + แผนของวันนั้น -----------------
    budget_obj = (
        DailyBudget.objects
        .filter(user=request.user, date=the_date)
        .order_by("-plan__id", "id")
        .first()
    )
    budget_amount = budget_obj.amount if budget_obj else 0
    current_plan = budget_obj.plan if budget_obj else None

    # ----------------- ดึงค่าใช้จ่ายของวันนั้น (ทุกอย่าง) -----------------
    all_spends = (
        BudgetSpend.objects
        .filter(user=request.user, date=the_date)
        .select_related("menu")
        .order_by("created_at")
    )

    # ใช้ทุก spend ในวันนั้นมาคำนวณยอดรวมในหัวข้อ
    spent_sum = all_spends.aggregate(total=Sum("amount"))["total"] or 0
    remain = budget_amount - spent_sum

    # ----------------- เลือก "รายการในแผน" ให้ถูกแผน -----------------
    # ถ้ามี plan ของวันนั้น และมี spend ที่อ้างอิงแผนนั้น -> ใช้เฉพาะของแผนนั้น
    if current_plan:
        plan_spends_qs = all_spends.filter(plan=current_plan)
        if plan_spends_qs.exists():
            plan_spends = list(plan_spends_qs)
        else:
            # กรณีข้อมูลเก่าที่ยังไม่มี plan ใน BudgetSpend -> ใช้ทั้งหมดเป็นแผน
            plan_spends = list(all_spends)
    else:
        # ถ้าไม่มี DailyBudget หรือไม่มี plan -> ใช้ทั้งหมดเป็น "แผนของวันนี้"
        plan_spends = list(all_spends)

    # ----------------- แยกตามมื้ออาหาร -----------------
    MEAL_LABELS = ["มื้อเช้า", "มื้อเที่ยง", "มื้อเย็น"]
    grouped = {label: [] for label in MEAL_LABELS}
    other_spends = []

    for s in plan_spends:
        if s.note in MEAL_LABELS:
            grouped[s.note].append(s)
        else:
            other_spends.append(s)

    meal_groups = [
        {"label": label, "items": grouped[label]}
        for label in MEAL_LABELS
    ]

    # ----------------- แนะนำสูตรอาหารจากชื่อเมนู -----------------
    # ใช้เฉพาะเมนูที่อยู่ใน "แผน" (plan_spends) เพื่อให้ตรงกับความต้องการ
    menu_names = []
    for s in plan_spends:
        if s.menu and s.menu.name:
            menu_names.append(s.menu.name.strip())

    suggested_recipes = []
    seen_recipe_ids = set()

    for name in menu_names:
        if not name:
            continue
        # หา Recipe ที่ title คล้ายกับชื่อเมนู
        qs = (
            Recipe.objects
            .filter(title__icontains=name)
            .order_by("-created_at")[:2]
        )
        for r in qs:
            if r.id not in seen_recipe_ids:
                seen_recipe_ids.add(r.id)
                suggested_recipes.append(r)

    context = {
        "date": the_date,
        "budget_amount": budget_amount,
        "spent_sum": spent_sum,
        "remain": remain,
        "meal_groups": meal_groups,        # ใช้ใน template แสดงตามมื้อ
        "other_spends": other_spends,      # รายการอื่น ๆ (เช่น กินข้างนอก)
        "suggested_recipes": suggested_recipes,
        "week_start": the_date - timedelta(days=the_date.weekday()),
    }
    return render(request, "budgets/day_detail.html", context)
# ----------------- ลบรายการใช้จ่าย -----------------
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

# ----------------- ตั้งงบทั้งสัปดาห์ -----------------
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
    for i in range(7):
        d = start_date + timedelta(days=i)
        obj, _ = _safe_get_or_create_daily(request, d)
        obj.amount = amount
        obj.save(update_fields=["amount"])

    messages.success(
        request,
        f"ตั้งงบ {amount} บาท/วัน สำหรับสัปดาห์ที่เริ่ม {start_date} เรียบร้อย",
    )
    return redirect(f"/budget/?start={start_date.isoformat()}")


# ---------- Alias รองรับโค้ดเดิม ----------
@require_POST
def save_expense(request):
    return consume_outside(request)


@require_POST
def save_menu_expense(request, menu_id: int):
    return consume_menu(request, menu_id)
