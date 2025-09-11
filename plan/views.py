# plan/views.py
from __future__ import annotations

from datetime import date
from typing import Iterable, List, Tuple

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.utils import timezone

from menus.models import Menu
from menus.utils import filter_by_plan  # << ใช้ตัวกรองตามข้อจำกัด


# --------------------------
# helpers
# --------------------------
def _parse_int(v, default: int) -> int:
    try:
        return int(v)
    except Exception:
        return default


def _parse_date(s: str | None) -> str:
    """
    รับสตริงวันแบบ YYYY-MM-DD ถ้าผิดฟอร์แมตให้คืนค่าวันปัจจุบัน
    (เก็บเป็นสตริงใน session ตามเดิมเพื่อไม่ต้องแก้ template อื่น)
    """
    if not s:
        return timezone.localdate().isoformat()
    try:
        # แค่ตรวจสอบว่า parse ได้
        date.fromisoformat(s)
        return s
    except Exception:
        return timezone.localdate().isoformat()


def _take_distinct(qs: Iterable[Menu], n: int, used_ids: set[int]) -> List[Menu]:
    """ดึงเมนู n รายการ โดยเลี่ยง id ที่อยู่ใน used_ids ให้มากที่สุด"""
    picked: List[Menu] = []
    for m in qs:
        if len(picked) >= n:
            break
        if m.id in used_ids:
            continue
        picked.append(m)
        used_ids.add(m.id)
    return picked


# --------------------------
# views
# --------------------------
@login_required
def plan_start_view(request):
    """
    รับค่าจาก popup เริ่มวางแผน -> เก็บลง session แล้วไป summary
    """
    if request.method == "POST":
        days = _parse_int(request.POST.get("days", "1"), 1)
        budget = _parse_int(request.POST.get("budget", "50"), 50)
        start_date = _parse_date(request.POST.get("start_date", ""))

        # รักษาค่าข้อจำกัดเดิมถ้ามีอยู่แล้วใน session
        old = request.session.get("plan", {})
        request.session["plan"] = {
            "days": days,
            "budget": budget,
            "start_date": start_date,
            "allergies": old.get("allergies", []),
            "dislikes": old.get("dislikes", []),
            "religions": old.get("religions", []),
            "extra": old.get("extra", {}),
        }
        request.session.modified = True
        return redirect("plan:summary")

    # เปิดตรง ๆ (ไม่ผ่าน POST) – ส่งค่าพื้นฐานให้ฟอร์ม
    return render(
        request,
        "accounts/plan_diet.html",
        {
            "budget": request.GET.get("budget", "50"),
            "days": request.GET.get("days", "1"),
            "start_date": request.GET.get("start_date", ""),
            "allergy_choices": ["กุ้ง", "นม", "แป้งสาลี", "ไข่", "ถั่ว", "ทะเล (รวม)"],
            "dislike_choices": ["หมู", "ไก่", "เห็ด", "หัวหอม", "เครื่องใน", "ผักชี", "กระเทียม", "เนื้อวัว"],
            "religion_choices": ["ฮาลาล", "มังสวิรัติ", "อาหารเจ", "หลีกเลี่ยงแอลกอฮอล์"],
        },
    )


@login_required
def mealplan_summary(request):
    """
    สรุปแผน: เลือกเมนูสำหรับ มื้อเช้า/เที่ยง/เย็น ตาม 'งบ + ข้อจำกัด' ใน session
    - ใช้ menus.utils.filter_by_plan() เพื่อตัดเมนูที่มีวัตถุดิบ/ข้อห้าม (เช่น 'หมู')
    - กระจายเมนูไม่ให้ซ้ำระหว่างมื้อ
    """
    plan = request.session.get("plan")
    if not plan:
        messages.info(request, "กรุณาเริ่มวางแผนก่อน")
        return redirect("plan:start")

    # ดึงเมนูทั้งหมด -> กรองตามข้อจำกัดในแผน -> กรองงบ (ถ้าไม่ใส่ในแผนจะ fallback เป็น 50)
    budget = _parse_int(plan.get("budget", 50), 50)
    base_qs = Menu.objects.all().order_by("-created_at")
    base_qs = filter_by_plan(base_qs, plan)   # << เคารพ allergies/dislikes/religions
    base_qs = base_qs.filter(price__lte=budget)

    # กระจายเมนู 3 มื้อ มื้อละ 2 รายการ (ปรับตัวเลขได้)
    used: set[int] = set()
    breakfast = _take_distinct(base_qs, 2, used)
    lunch     = _take_distinct(base_qs, 2, used)
    dinner    = _take_distinct(base_qs, 2, used)

    sections: List[Tuple[str, List[Menu]]] = [
        ("มื้อเช้า", breakfast),
        ("มื้อเที่ยง", lunch),
        ("มื้อเย็น", dinner),
    ]

    return render(
        request,
        "plan/summary.html",
        {
            "plan": plan,
            "sections": sections,
            "today": timezone.localdate(),
        },
    )
