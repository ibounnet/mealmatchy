# accounts/views.py
from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.admin.views.decorators import staff_member_required
from django.utils import timezone
from django.apps import apps

from .forms import (
    CustomUserCreationForm,
    UserUpdateForm,
    ProfileUpdateForm,
    LoginForm,
)
from .models import Profile

from menus.models import Menu, Ingredient
from restaurants.models import Restaurant
from budgets.models import MealPlan, BudgetSpend

MEAL_LABELS = ["มื้อเช้า", "มื้อเที่ยง", "มื้อเย็น"]


def _meal_status_for_date(user, the_date, plan=None):
    qs = BudgetSpend.objects.filter(user=user, date=the_date, note__in=MEAL_LABELS)
    if plan:
        qs = qs.filter(plan=plan)

    done_set = set(qs.values_list("note", flat=True)) 
    done_set = set(qs.values_list("note", flat=True)) 
    done_labels = [x for x in MEAL_LABELS if x in done_set] #มื้อที่มีอยู่แล้ว
    missing_labels = [x for x in MEAL_LABELS if x not in done_set] #มื้ิอที่ยังไม่มี

    return {
        "done_labels": done_labels, 
        "missing_labels": missing_labels,
        "done_count": len(done_labels),
        "total": len(MEAL_LABELS),
        "is_complete": (len(done_labels) == len(MEAL_LABELS)), #ทำครบ3มื้อมมั้ย
    }


def _detect_user_field(Model):
    if not Model:
        return None
    candidate_names = ["user", "author", "created_by", "owner", "created_user", "posted_by"]
    model_fields = {f.name for f in Model._meta.get_fields()}
    for name in candidate_names:
        if name in model_fields:
            return name
    return None


def _find_model_by_names(model_names):
    model_names_lower = {m.lower() for m in model_names}
    for m in apps.get_models():
        if m.__name__.lower() in model_names_lower:
            return m
    return None


def home_view(request):
    try:
        budget = int(request.GET.get("budget", 50)) #อ่านงบ
    except (TypeError, ValueError):
        budget = 50

    menus = Menu.objects.filter(price__lte=budget, status=Menu.Status.APPROVED).order_by("-created_at")[:12] #ดึงเมนูราคาไม่เกินงบและต้องอนุมัติแล้ว

    ctx = {"budget": budget, "menus": menus, "today_meal_status": None, "today_date": None}

    if request.user.is_authenticated:
        today = timezone.localdate()
        ctx["today_date"] = today

        plan = None
        plan_id = request.session.get("active_plan_id")
        if plan_id:
            plan = MealPlan.objects.filter(id=plan_id, user=request.user).first()

        if plan:
            plan_end = plan.start_date + timezone.timedelta(days=plan.days - 1)
            if plan.start_date <= today <= plan_end:
                ctx["today_meal_status"] = _meal_status_for_date(request.user, today, plan)

    return render(request, "accounts/home.html", ctx)


# ====================== AUTH ======================

def register_view(request):
    if request.method == "POST":
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "สมัครสมาชิกสำเร็จ! ลองล็อกอินได้เลย")
            return redirect("accounts:login")
        messages.error(request, "กรุณาตรวจสอบข้อมูลให้ถูกต้อง")
    else:
        form = CustomUserCreationForm()
    return render(request, "accounts/register.html", {"form": form})


def login_view(request):
    """
    ✅ ถ้า login แล้วเป็น staff/superuser -> เข้า admin dashboard ทันที
    """
    if request.method == "POST":
        form = LoginForm(request, data=request.POST)
        if form.is_valid():
            login(request, form.get_user())

            # ✅ redirect ตาม role
            u = request.user
            if u.is_staff or u.is_superuser:
                return redirect("accounts:admin_dashboard")

            # ถ้า user ทั่วไป ให้ไปหน้า home (หรือจะใช้ next ก็ได้)
            return redirect("home")

        messages.error(request, "ชื่อผู้ใช้หรือรหัสผ่านไม่ถูกต้อง")
    else:
        form = LoginForm(request)

    return render(request, "accounts/login.html", {"form": form})


def logout_view(request):
    logout(request)
    return redirect("accounts:login")


# ====================== PROFILE ======================

@login_required
def profile_remove_image_view(request):
    if request.method != "POST":
        return redirect("accounts:profile")

    profile, _ = Profile.objects.get_or_create(user=request.user)
    if profile.profile_picture:
        profile.profile_picture.delete(save=False)
        profile.profile_picture = None
        profile.save()
        messages.success(request, "ลบรูปโปรไฟล์เรียบร้อยแล้ว")
    else:
        messages.info(request, "ยังไม่มีรูปโปรไฟล์")

    return redirect("accounts:profile")


@login_required
def profile_view(request):
    profile, _ = Profile.objects.get_or_create(user=request.user)

    if request.method == "POST":
        uform = UserUpdateForm(request.POST, instance=request.user)
        pform = ProfileUpdateForm(request.POST, request.FILES, instance=profile)

        if uform.is_valid() and pform.is_valid():
            uform.save()
            pform.save()
            messages.success(request, "อัปเดตโปรไฟล์เรียบร้อยแล้ว")
            return redirect("accounts:profile")

        messages.error(request, "บันทึกไม่สำเร็จ: กรุณาตรวจสอบข้อมูลในฟอร์ม")
    else:
        uform = UserUpdateForm(instance=request.user)
        pform = ProfileUpdateForm(instance=profile)

    today = timezone.localdate()
    active_plan = None
    active_plan_end = None

    plan_id = request.session.get("active_plan_id")
    if plan_id:
        active_plan = MealPlan.objects.filter(id=plan_id, user=request.user).first()

    if active_plan:
        active_plan_end = active_plan.start_date + timezone.timedelta(days=active_plan.days - 1)

    return render(
        request,
        "accounts/profile.html",
        {
            "uform": uform,
            "pform": pform,
            "profile": profile,
            "today": today,
            "active_plan": active_plan,
            "active_plan_end": active_plan_end,
        },
    )


# ======================
# ADMIN DASHBOARD (แยก Layout)
# ======================

@staff_member_required
def admin_dashboard_view(request):
    """
    Render: templates/admin/dashboard.html
    """
    pending_menus = Menu.objects.filter(status=Menu.Status.PENDING).count()
    pending_restaurants = Restaurant.objects.filter(is_active=False).count()
    ingredient_count = Ingredient.objects.count()

    # หาระบบ community แบบยืดหยุ่น (ตามชื่อที่มักใช้)
    TopicModel = _find_model_by_names(["Topic", "Post", "CommunityPost"])
    ReviewModel = _find_model_by_names(["Review"])

    topic_count = TopicModel.objects.count() if TopicModel else 0
    review_count = ReviewModel.objects.count() if ReviewModel else 0

    ctx = {
        "pending_menus": pending_menus,
        "pending_restaurants": pending_restaurants,
        "ingredient_count": ingredient_count,
        "topic_count": topic_count,
        "review_count": review_count,
    }
    return render(request, "admin/dashboard.html", ctx)
