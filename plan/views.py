from __future__ import annotations
from datetime import date, timedelta
from typing import List, Tuple
import json, random

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
    """
    เริ่มวางแผนจาก popup (หน้าแรก)

    ทุกครั้งที่ผู้ใช้เริ่มแผนใหม่:
    - reset ตัวเลือกเมนูเก่าและ active_plan_id ทิ้ง
    """
    if request.method == 'POST':
        days = _parse_int(request.POST.get('days', '1'), 1)
        budget = _parse_int(request.POST.get('budget', '50'), 50)
        start_date = _parse_date(request.POST.get('start_date', ''))

        old = request.session.get('plan', {})

        request.session['plan'] = {
            'days': days,
            'budget': budget,
            'start_date': start_date.isoformat(),
            'allergies': old.get('allergies', []),
            'dislikes':  old.get('dislikes',  []),
            'religions': old.get('religions', []),
            'extra': old.get('extra', {}),
        }

        request.session.pop('selected_menus', None)
        request.session.pop('active_plan_id', None)
        request.session.modified = True

        return redirect('plan:diet')

    # ถ้าเป็น GET ก็ถือว่าเริ่มใหม่เหมือนกัน
    request.session.pop('selected_menus', None)
    request.session.pop('active_plan_id', None)
    request.session.modified = True
    return redirect('plan:diet')


@login_required
def plan_diet(request):
    """หน้าเลือกข้อจำกัดอาหาร"""
    plan = request.session.get('plan', {
        'days': 1, 'budget': 50, 'start_date': timezone.localdate().isoformat()
    })

    allergy_choices  = ["กุ้ง", "นม", "แป้งสาลี", "ไข่", "ถั่ว", "ทะเล"]
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
    """
    หน้าสรุปแผน:
    - สุ่มร้าน -> ดึงเมนูของร้าน
    - ใช้ selected_menus จาก session เป็นค่าเริ่มต้น (ค้างเมนูเดิมไว้)
    """
    plan = request.session.get('plan')
    if not plan:
        messages.info(request, "กรุณาเริ่มวางแผนก่อน")
        return redirect('plan:start')

    budget = _parse_int(plan.get('budget', 0), 0)

    # สุ่มร้าน 3 ร้าน
    all_ids = list(Restaurant.objects.values_list("id", flat=True))
    picked_ids = random.sample(all_ids, min(3, len(all_ids))) if all_ids else []
    restaurants = Restaurant.objects.filter(id__in=picked_ids)

    data: List[Tuple[Restaurant, List[Menu]]] = []
    for r in restaurants:
        menus = Menu.objects.filter(restaurant=r)
        menus = filter_by_plan(menus, plan)
        if budget > 0:
            menus = menus.filter(price__lte=budget)
        data.append((r, list(menus)))

    # อ่านเมนูที่เลือกค้างไว้จาก session
    selected_menus = request.session.get("selected_menus", [])

    return render(request, "plan/summary.html", {
        "plan": plan,
        "restaurant_menus": data,
        "meal_choices": ["มื้อเช้า", "มื้อเที่ยง", "มื้อเย็น"],
        "today": timezone.localdate(),
        "selected_menus_json": json.dumps(selected_menus, ensure_ascii=False),
    })


@login_required
@require_POST
def save_plan(request):
    """
    รับ selections จาก summary (JSON: [{id, name, price, meal, ...}, ...])

    ปรับ logic ใหม่:
    - มองว่าเป็น "แผนต่อวัน" ถ้าบันทึกซ้ำในช่วงวันที่เดิม
      ให้ลบแผนเก่า + รายการใช้จ่ายเก่าของช่วงนั้นทิ้งก่อน แล้วค่อยสร้างใหม่
      ทำให้ยอด 'ใช้ไป' ไม่เพิ่มซ้ำทุกครั้งที่กดบันทึก
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
    end_date = start_date + timedelta(days=days)

    # 1) ลบแผนเก่า + รายการใช้งบเก่าของช่วงวันเดียวกัน (เฉพาะที่มาจากแผน)
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
            date__lt=end_date,
        ).delete()

        DailyBudget.objects.filter(
            user=request.user,
            plan__in=old_plans,
            date__gte=start_date,
            date__lt=end_date,
        ).delete()

        old_plans.delete()

    # 2) สร้างแผนใหม่
    plan_obj = MealPlan.objects.create(
        user=request.user,
        start_date=start_date,
        days=days,
        budget_per_day=budget,
        title=sess.get("title", ""),
    )

    request.session["active_plan_id"] = plan_obj.id
    request.session["selected_menus"] = menus  # เก็บไว้ให้ค้างเมนูตอนกลับมาดู
    request.session.modified = True

    # 3) สร้าง DailyBudget สำหรับแต่ละวัน (ใช้ update_or_create เผื่อเคยมีบันทึก)
    for i in range(days):
        d = start_date + timedelta(days=i)
        DailyBudget.objects.update_or_create(
            user=request.user,
            date=d,
            plan=plan_obj,
            defaults={"amount": budget},
        )

    # 4) บันทึก BudgetSpend ของเมนูที่เลือก (ตอนนี้จะมีชุดเดียว ไม่ซ้ำกับของเดิมแล้ว)
    for m in menus:
        menu = Menu.objects.filter(pk=m.get("id")).first()
        if not menu:
            continue

        BudgetSpend.objects.create(
            user=request.user,
            date=start_date,        # ถ้าต่อไปอยากแยกเป็นวัน-มื้อ ค่อยกระจายวันที่ทีหลัง
            amount=menu.price,
            menu=menu,
            plan=plan_obj,
            note=(m.get("meal") or ""),
        )

    messages.success(request, "บันทึกแผนเรียบร้อยแล้ว")
    return redirect("/budget/?from_plan=1")
