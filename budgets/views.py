# budgets/views.py
from datetime import timedelta
from django.db.models import Sum
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.views.decorators.http import require_POST

from .models import DailyBudget, BudgetSpend
from .forms import DailyBudgetForm
from menus.models import Menu


def _monday(date):
    """คืนวันจันทร์ของสัปดาห์ที่ date อยู่"""
    return date - timedelta(days=date.weekday())


def _parse_date_or_today(date_str: str | None):
    """รับ YYYY-MM-DD -> date; ถ้า None/ว่าง ใช้วันนี้"""
    if date_str:
        return timezone.datetime.fromisoformat(date_str).date()
    return timezone.localdate()


def _default_budget_from_session(request) -> int:
    """ดึงงบ default จากแผนใน session (ถ้ามี)"""
    plan = request.session.get('plan') or {}
    b = plan.get('budget')
    try:
        return int(b)
    except Exception:
        return 0


def _safe_get_or_create_daily(request, use_date):
    """
    ดึง/สร้าง DailyBudget ของ user+date แบบปลอดภัย:
    - ถ้ามีหลายแถว (ข้อมูลซ้ำ) จะเลือก id ต่ำสุดมาใช้
    - ถ้าไม่มี -> สร้างใหม่ด้วยงบ default จาก session
    """
    qs = DailyBudget.objects.filter(user=request.user, date=use_date).order_by('id')
    if qs.exists():
        return qs.first(), False
    return DailyBudget.objects.create(
        user=request.user,
        date=use_date,
        amount=_default_budget_from_session(request)
    ), True


# ================= ตารางรายสัปดาห์ =================

@login_required
def budget_table(request):
    """
    ตารางรายสัปดาห์: แสดงเฉพาะวัน/งบที่ผู้ใช้ตั้งไว้จริงในสัปดาห์นั้น
    สลับสัปดาห์ด้วย ?start=YYYY-MM-DD (ควรเป็นวันจันทร์)
    """
    start_date = _parse_date_or_today(request.GET.get('start'))
    start_date = _monday(start_date)
    end_date = start_date + timedelta(days=6)

    budgets_qs = DailyBudget.objects.filter(
        user=request.user, date__range=[start_date, end_date]
    ).order_by('date')

    planned_dates = [b.date for b in budgets_qs]

    spends_qs = BudgetSpend.objects.filter(user=request.user, date__in=planned_dates)
    spends_sum = spends_qs.values('date').annotate(total=Sum('amount'))
    spends_map = {row['date']: row['total'] or 0 for row in spends_sum}

    rows = []
    for b in budgets_qs:
        spent = spends_map.get(b.date, 0)
        day_spends = (BudgetSpend.objects
                      .filter(user=request.user, date=b.date)
                      .select_related('menu')
                      .order_by('-created_at'))
        rows.append({
            'date': b.date,
            'budget_amount': b.amount,
            'spent_amount': spent,
            'remain_amount': b.amount - spent,
            'spends': day_spends,
        })

    return render(request, 'budgets/budget_table.html', {
        'rows': rows,
        'start_date': start_date,
        'prev_start': start_date - timedelta(days=7),
        'next_start': start_date + timedelta(days=7),
    })


# ================= ตั้ง/แก้งบรายวัน =================

@login_required
def set_daily_budget(request, date_str=None):
    """
    หน้าตั้ง/แก้ไขงบรายวัน
    GET มีค่า date_str จะเติมลงฟอร์มให้
    """
    initial_date = None
    if date_str:
        initial_date = _parse_date_or_today(date_str)

    if request.method == 'POST':
        form = DailyBudgetForm(request.POST)
        if form.is_valid():
            d = form.cleaned_data['date']
            amt = form.cleaned_data['amount']
            # อนุญาตมีซ้ำใน DB เก่า -> เลือกตัวแรกแล้วอัปเดต
            obj, created = _safe_get_or_create_daily(request, d)
            obj.amount = amt
            obj.save(update_fields=['amount'])
            messages.success(request, f'บันทึกงบ {d} = {amt} บาท')
            return redirect(f"/budget/?start={_monday(d).isoformat()}")
    else:
        initial = {}
        if initial_date:
            initial['date'] = initial_date
            exist = DailyBudget.objects.filter(user=request.user, date=initial_date).order_by('id').first()
            if exist:
                initial['amount'] = exist.amount
        form = DailyBudgetForm(initial=initial)

    return render(request, 'budgets/set_daily_budget.html', {'form': form})


# ================= บันทึกค่าใช้จ่าย =================

@login_required
@require_POST
def consume_menu(request, menu_id: int):
    """
    บันทึกการใช้จ่ายจาก 'เมนู' ในระบบ และผูกกับ DailyBudget ของวันนั้น
    - ถ้าวันนั้นยังไม่มี DailyBudget สร้างใหม่โดยใช้งบจาก session ถ้ามี
    - ถ้าฐานข้อมูลมีงบวันนั้นมากกว่า 1 แถว จะหยิบแถวแรกมาใช้
    """
    menu = get_object_or_404(Menu, pk=menu_id)
    use_date = _parse_date_or_today(request.POST.get('date'))

    daily_obj, _ = _safe_get_or_create_daily(request, use_date)

    BudgetSpend.objects.create(
        user=request.user,
        date=use_date,
        amount=menu.price,
        menu=menu,
        note=f"กินเมนู {menu.name}",
    )

    messages.success(
        request,
        f"บันทึก {menu.name} {menu.price} บาท "
        f"(วันที่ {use_date}, งบ {daily_obj.amount} บาท)"
    )
    return redirect(f"/budget/?start={_monday(use_date).isoformat()}")


@login_required
@require_POST
def consume_outside(request):
    """
    บันทึกค่าใช้จ่ายอิสระ/กินข้างนอก
    """
    try:
        amount = int(request.POST.get('amount', '0') or 0)
    except Exception:
        amount = 0
    note = (request.POST.get('note') or '').strip()
    use_date = _parse_date_or_today(request.POST.get('date'))

    if amount <= 0:
        messages.error(request, "กรุณาระบุจำนวนเงินให้ถูกต้อง")
        return redirect('/budget/')

    _safe_get_or_create_daily(request, use_date)

    BudgetSpend.objects.create(
        user=request.user,
        date=use_date,
        amount=amount,
        note=note or "กินข้างนอก",
    )
    messages.success(request, f"บันทึกการใช้จ่าย {amount} บาท (วันที่ {use_date})")
    return redirect(f"/budget/?start={_monday(use_date).isoformat()}")


# ================= รายละเอียดรายวัน / ลบรายการ =================

@login_required
def day_detail(request, date_str):
    """
    หน้ารายละเอียดต่อวัน (งบ, ใช้ไป, คงเหลือ, รายการใช้จ่าย)
    """
    the_date = _parse_date_or_today(date_str)

    budget_obj = DailyBudget.objects.filter(user=request.user, date=the_date).order_by('id').first()
    budget_amount = budget_obj.amount if budget_obj else 0

    spends = (BudgetSpend.objects
              .filter(user=request.user, date=the_date)
              .select_related('menu')
              .order_by('-created_at'))

    spent_sum = spends.aggregate(total=Sum('amount'))['total'] or 0
    remain = budget_amount - spent_sum

    return render(request, 'budgets/day_detail.html', {
        'date': the_date,
        'budget_amount': budget_amount,
        'spent_sum': spent_sum,
        'remain': remain,
        'spends': spends,
        'week_start': _monday(the_date),
    })


@login_required
@require_POST
def delete_spend(request, pk):
    obj = get_object_or_404(BudgetSpend, pk=pk, user=request.user)
    d = obj.date
    obj.delete()
    messages.success(request, 'ลบรายการเรียบร้อยแล้ว')
    return redirect('budgets:day_detail', date_str=d.isoformat())


# ================= ตั้งงบทั้งสัปดาห์ =================

@login_required
@require_POST
def set_week_same_amount(request):
    """
    ตั้งงบเท่ากันทั้งสัปดาห์ (จาก start=วันจันทร์ และ amount)
    """
    try:
        amount = int(request.POST.get('amount', '0') or 0)
    except Exception:
        amount = 0
    start_str = request.POST.get('start')

    if amount <= 0 or not start_str:
        messages.error(request, 'กรุณากรอกจำนวนเงินและสัปดาห์ให้ถูกต้อง')
        return redirect('/budget/')

    start_date = _parse_date_or_today(start_str)
    for i in range(7):
        d = start_date + timedelta(days=i)
        obj, _ = _safe_get_or_create_daily(request, d)
        obj.amount = amount
        obj.save(update_fields=['amount'])

    messages.success(request, f'ตั้งงบ {amount} บาท/วัน สำหรับสัปดาห์ที่เริ่ม {start_date} เรียบร้อย')
    return redirect(f"/budget/?start={start_date.isoformat()}")


# ---------- Alias รองรับโค้ดเดิม ----------
@require_POST
def save_expense(request):
    return consume_outside(request)


@require_POST
def save_menu_expense(request, menu_id: int):
    return consume_menu(request, menu_id)
