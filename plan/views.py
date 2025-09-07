# plan/views.py
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from menus.models import Menu
from django.utils import timezone

@login_required
def plan_start_view(request):
    """
    รับค่าจาก popup เริ่มวางแผน -> เก็บลง session แล้วพาไป summary
    """
    if request.method == "POST":
        # รับจากฟอร์ม popup
        days       = request.POST.get("days", "1")
        start_date = request.POST.get("start_date", "")
        budget     = request.POST.get("budget", "50")

        # เก็บไว้ใน session (อย่างน้อยต้องมี budget)
        try:
            budget_int = int(budget)
        except ValueError:
            budget_int = 50

        request.session["plan"] = {
            "days": int(days) if str(days).isdigit() else 1,
            "start_date": start_date,
            "budget": budget_int,
            # ช่องข้อจำกัด ต่าง ๆ (ถ้ายังไม่มี ก็ใส่เป็นลิสต์ว่างไว้ก่อน)
            "allergies": request.session.get("plan", {}).get("allergies", []),
            "dislikes":  request.session.get("plan", {}).get("dislikes",  []),
            "religions": request.session.get("plan", {}).get("religions", []),
        }
        request.session.modified = True
        return redirect("plan:summary")

    # เปิดตรง ๆ จะให้กรอก popup อีกครั้ง (หรือจะ redirect ไปหน้า home ก็ได้)
    return render(request, "accounts/plan_diet.html", {
        "budget": request.GET.get("budget", "50"),
        "days": request.GET.get("days", "1"),
        "start_date": request.GET.get("start_date", ""),
        # ใส่ตัวเลือกพื้นฐานถ้าคุณใช้ในฟอร์มข้อจำกัด (ถ้าไม่ใช้ ลบได้)
        "allergy_choices":  ["กุ้ง","นม","แป้งสาลี","ไข่","ถั่ว","ทะเล (รวม)"],
        "dislike_choices":  ["หมู","ไก่","เห็ด","หัวหอม","เครื่องใน","ผักชี","กระเทียม","เนื้อวัว"],
        "religion_choices": ["ฮาลาล","มังสวิรัติ","อาหารเจ","หลีกเลี่ยงแอลกอฮอล์"],
    })


@login_required
def mealplan_summary(request):
    """
    สรุปแผน: เลือกเมนูสำหรับ มื้อเช้า/เที่ยง/เย็น ตามงบ + ข้อจำกัดใน session
    """
    plan = request.session.get("plan")
    if not plan:
        messages.info(request, "กรุณาเริ่มวางแผนก่อน")
        return redirect("plan:start")

    budget = plan.get("budget", 50)

    # *** ตรงนี้คุณสามารถกรองตามข้อจำกัดได้ตามที่วางไว้ในโปรเจคจริง ***
    # อย่างต่ำให้แสดงเมนูตามงบก่อน
    base_qs = Menu.objects.filter(price__lte=budget).order_by("-created_at")

    # เลือกมาอย่างละ 3 รายการเป็นตัวอย่าง
    breakfast = list(base_qs[:3])
    lunch     = list(base_qs[3:6]) if base_qs.count() >= 6 else list(base_qs[:3])
    dinner    = list(base_qs[6:9]) if base_qs.count() >= 9 else list(base_qs[:3])

    # ✅ สำคัญ: เตรียมลิสต์ sections จากฝั่ง view ก่อน แล้วค่อยไปวนใน template
    sections = [
        ("มื้อเช้า",  breakfast),
        ("มื้อเที่ยง", lunch),
        ("มื้อเย็น",  dinner),
    ]

    return render(request, "plan/summary.html", {
        "plan": plan,
        "sections": sections,   # ← ใช้ตัวนี้ใน template
        "today": timezone.localdate(),
    })
