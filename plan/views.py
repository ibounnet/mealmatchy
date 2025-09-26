# plan/views.py
from __future__ import annotations
from datetime import date
from typing import Iterable, List, Tuple

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.utils import timezone

from menus.models import Menu
from menus.utils import filter_by_plan


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

def _take_distinct(qs: Iterable[Menu], n: int, used_ids: set[int]) -> List[Menu]:
    picked: List[Menu] = []
    for m in qs:
        if len(picked) >= n:
            break
        if m.id in used_ids:
            continue
        picked.append(m)
        used_ids.add(m.id)
    return picked


# เริ่มวางแผนจาก popup (home)
@login_required
def plan_start(request):
    if request.method == 'POST':
        days = _parse_int(request.POST.get('days', '1'), 1)
        budget = _parse_int(request.POST.get('budget', '50'), 50)
        start_date = _parse_date(request.POST.get('start_date', ''))

        # เก็บ/ผสมข้อมูลเก่าใน session
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


# หน้าเลือกข้อจำกัดอาหาร
@login_required
def plan_diet(request):
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


# หน้าสรุปก่อนเข้า budget/เมนู
@login_required
def mealplan_summary(request):
    plan = request.session.get('plan')
    if not plan:
        # แก้ไม่ให้ messages ซ้ำ
        storage = messages.get_messages(request)
        if not any(m.message == "กรุณาเริ่มวางแผนก่อน" for m in storage):
            messages.info(request, "กรุณาเริ่มวางแผนก่อน")
        return redirect('plan:start')

    # ใช้งบที่กรอกมาจริง ๆ ไม่บังคับ 50
    budget = _parse_int(plan.get('budget', 0), 0)

    base_qs = Menu.objects.all().order_by("-created_at")
    base_qs = filter_by_plan(base_qs, plan)
    if budget > 0:
        base_qs = base_qs.filter(price__lte=budget)

    used: set[int] = set()
    breakfast = _take_distinct(base_qs, 2, used)
    lunch     = _take_distinct(base_qs, 2, used)
    dinner    = _take_distinct(base_qs, 2, used)

    sections: List[Tuple[str, List[Menu]]] = [
        ("มื้อเช้า", breakfast),
        ("มื้อเที่ยง", lunch),
        ("มื้อเย็น", dinner),
    ]

    return render(request, "plan/summary.html", {
        "plan": plan,
        "sections": sections,
        "today": timezone.localdate(),
    })


# ฟังก์ชันแก้ไขงบ (ใช้จากปุ่ม "แก้งบ")
@login_required
def update_budget(request):
    if request.method == "POST":
        plan = request.session.get('plan')
        if not plan:
            messages.error(request, "ไม่พบแผนที่จะปรับงบ")
            return redirect('plan:start')

        new_budget = _parse_int(request.POST.get("budget", plan.get("budget", 0)), 0)
        plan['budget'] = new_budget
        request.session['plan'] = plan
        request.session.modified = True
        messages.success(request, "แก้งบประมาณเรียบร้อย")
        return redirect("plan:summary")
