from __future__ import annotations
from datetime import date
from typing import Iterable, List, Tuple
import json, random

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST
from django.utils import timezone

from budgets.models import BudgetSpend, DailyBudget
from menus.models import Menu, Restaurant   # ✅ import Restaurant
from menus.utils import filter_by_plan


# ----------------- helpers -----------------
def _parse_int(v, default: int) -> int:
    try:
        return int(v)
    except Exception:
        return default


def _parse_date(s: str | None) -> str:
    if not s:
        return timezone.localdate().isoformat()
    try:
        date.fromisoformat(s)
        return s
    except Exception:
        return timezone.localdate().isoformat()


# ----------------- views -----------------
@login_required
def plan_start(request):
    """เริ่มวางแผนจาก popup (หน้าแรก)"""
    if request.method == 'POST':
        days = _parse_int(request.POST.get('days', '1'), 1)
        budget = _parse_int(request.POST.get('budget', '50'), 50)
        start_date = _parse_date(request.POST.get('start_date', ''))

        old = request.session.get('plan', {})
        request.session['plan'] = {
            'days': days,
            'budget': budget,
            'start_date': start_date,
            'allergies': old.get('allergies', []),
            'dislikes':  old.get('dislikes',  []),
            'religions': old.get('religions', []),
            'extra': old.get('extra', {}),
        }
        request.session.modified = True
        return redirect('plan:diet')

    return redirect('plan:diet')


@login_required
def plan_diet(request):
    """หน้าเลือกข้อจำกัดอาหาร"""
    plan = request.session.get('plan', {
        'days': 1, 'budget': 50, 'start_date': timezone.localdate().isoformat()
    })

    allergy_choices  = ["กุ้ง", "นม", "แป้งสาลี", "ไข่", "ถั่ว", "ทะเล (รวม)"]
    dislike_choices  = ["หมู", "ไก่", "เห็ด", "หัวหอม", "เครื่องใน", "ผักชี", "กระเทียม", "เนื้อวัว"]
    religion_choices = ["ฮาลาล", "มังสวิรัติ", "อาหารเจ", "หลีกเลี่ยงแอลกอฮอล์"]

    if request.method == 'POST':
        allergies = request.POST.getlist('allergies')
        dislikes  = request.POST.getlist('dislikes')
        religions = request.POST.getlist('religions')

        request.session['plan'].update({
            'allergies': allergies,
            'dislikes': dislikes,
            'religions': religions,
            'extra': {
                'allergy': request.POST.get('extra_allergy', '').strip(),
                'dislike': request.POST.get('extra_dislike', '').strip(),
                'religion': request.POST.get('extra_religion', '').strip(),
            }
        })
        request.session.modified = True
        return redirect('plan:summary')

    return render(request, 'plan/plan_diet.html', {
        'plan': plan,
        'allergy_choices': allergy_choices,
        'dislike_choices': dislike_choices,
        'religion_choices': religion_choices,
    })


@login_required
def mealplan_summary(request):
    """หน้าสรุปแผน: สุ่มร้าน -> ดึงเมนูของร้าน"""
    plan = request.session.get('plan')
    if not plan:
        storage = messages.get_messages(request)
        if not any(m.message == "กรุณาเริ่มวางแผนก่อน" for m in storage):
            messages.info(request, "กรุณาเริ่มวางแผนก่อน")
        return redirect('plan:start')

    budget = _parse_int(plan.get('budget', 0), 0)

    # ✅ เลือกร้านแบบสุ่ม 3 ร้าน
    restaurant_ids = list(Restaurant.objects.values_list("id", flat=True))
    picked_ids = random.sample(restaurant_ids, min(3, len(restaurant_ids)))
    restaurants = Restaurant.objects.filter(id__in=picked_ids)

    data = []
    for r in restaurants:
        menus = Menu.objects.filter(restaurant=r)
        menus = filter_by_plan(menus, plan)
        if budget > 0:
            menus = menus.filter(price__lte=budget)
        data.append((r, menus))

    return render(request, "plan/summary.html", {
        "plan": plan,
        "restaurant_menus": data,
        "today": timezone.localdate(),
    })


@login_required
@require_POST
def save_plan(request):
    """บันทึกแผนเข้าฐานข้อมูล"""
    menus_json = request.POST.get("menus", "[]")
    try:
        menus = json.loads(menus_json)
    except json.JSONDecodeError:
        menus = []

    if not menus:
        messages.error(request, "กรุณาเลือกเมนูก่อนบันทึก")
        return redirect("plan:summary")

    plan = request.session.get("plan", {})
    use_date = plan.get("start_date") or date.today().isoformat()

    daily, _ = DailyBudget.objects.get_or_create(
        user=request.user,
        date=use_date,
        defaults={"amount": int(plan.get("budget") or 0)}
    )

    for m in menus:
        try:
            menu = Menu.objects.get(pk=m["id"])
            BudgetSpend.objects.create(
                user=request.user,
                date=use_date,
                amount=menu.price,
                menu=menu,
                note=f"เลือกในแผน {menu.name}",
            )
        except Menu.DoesNotExist:
            continue

    messages.success(request, "บันทึกแผนการกินเรียบร้อยแล้ว")
    return redirect("/budget/?from_plan=1")
