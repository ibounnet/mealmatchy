# accounts/views.py
from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.utils import timezone

from .forms import (
    CustomUserCreationForm,
    UserUpdateForm,
    ProfileUpdateForm,
    LoginForm,
)
from .models import Profile
from menus.models import Menu

from budgets.models import MealPlan, BudgetSpend


MEAL_LABELS = ["มื้อเช้า", "มื้อเที่ยง", "มื้อเย็น"]


def _meal_status_for_date(user, the_date, plan=None):
    """
    นับมื้อจาก BudgetSpend.note ที่ต้องเป็นหนึ่งใน MEAL_LABELS
    และต้องอยู่ใน plan เดียวกัน (ถ้ามี plan)
    """
    qs = BudgetSpend.objects.filter(
        user=user,
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


def home_view(request):
    """
    หน้าแรก: ปุ่มวางแผน + search + เมนูแนะนำในงบ + community
    + แถบเตือน "วันนี้ยังทำไม่ครบมื้อ" เฉพาะเมื่อ:
      - login
      - มี active_plan_id
      - วันนี้อยู่ในช่วงแผน
    """
    try:
        budget = int(request.GET.get('budget', 50))
    except (TypeError, ValueError):
        budget = 50

    menus = (
        Menu.objects.filter(price__lte=budget)
        .order_by('-created_at')[:12]
    )

    ctx = {
        'budget': budget,
        'menus': menus,
        'today_meal_status': None,
        'today_date': None,
    }

    if request.user.is_authenticated:
        today = timezone.localdate()
        ctx["today_date"] = today

        plan = None
        plan_id = request.session.get("active_plan_id")
        if plan_id:
            plan = MealPlan.objects.filter(id=plan_id, user=request.user).first()

        # โชว์แถบเฉพาะเมื่อมีแผน และวันนี้อยู่ในช่วงแผน
        if plan:
            plan_end = plan.start_date + timezone.timedelta(days=plan.days - 1)
            if plan.start_date <= today <= plan_end:
                ctx["today_meal_status"] = _meal_status_for_date(request.user, today, plan)

    return render(request, 'accounts/home.html', ctx)


# ====================== AUTH ======================

def register_view(request):
    if request.method == "POST":
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "สมัครสมาชิกสำเร็จ! ลองล็อกอินได้เลย")
            return redirect('login')
        messages.error(request, "กรุณาตรวจสอบข้อมูลให้ถูกต้อง")
    else:
        form = CustomUserCreationForm()
    return render(request, 'accounts/register.html', {'form': form})


def login_view(request):
    if request.method == 'POST':
        form = LoginForm(request, data=request.POST)
        if form.is_valid():
            login(request, form.get_user())
            return redirect('home')
        messages.error(request, "ชื่อผู้ใช้หรือรหัสผ่านไม่ถูกต้อง")
    else:
        form = LoginForm(request)
    return render(request, 'accounts/login.html', {'form': form})


def logout_view(request):
    logout(request)
    return redirect('login')


# ====================== PROFILE ======================

@login_required
def profile_view(request):
    profile, _ = Profile.objects.get_or_create(user=request.user)

    if request.method == 'POST':
        uform = UserUpdateForm(request.POST, instance=request.user)
        pform = ProfileUpdateForm(request.POST, request.FILES, instance=profile)
        if uform.is_valid() and pform.is_valid():
            uform.save()
            pform.save()
            messages.success(request, 'อัปเดตโปรไฟล์เรียบร้อยแล้ว')
            return redirect('profile')
        messages.error(request, 'กรุณาตรวจสอบข้อมูลให้ถูกต้อง')
    else:
        uform = UserUpdateForm(instance=request.user)
        pform = ProfileUpdateForm(instance=profile)

    return render(request, 'accounts/profile.html', {
        'uform': uform,
        'pform': pform,
        'profile': profile,
    })
