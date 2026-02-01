# accounts/views.py
from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.utils import timezone

from menus.models import Menu
from budgets.models import MealPlan, BudgetSpend

from .forms import (
    CustomUserCreationForm,
    UserUpdateForm,
    ProfileUpdateForm,
    LoginForm,
)
from .models import Profile

MEAL_LABELS = ["มื้อเช้า", "มื้อเที่ยง", "มื้อเย็น"]


def _meal_status_for_date(user, the_date, plan=None):
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
    # budget filter (default 50)
    try:
        budget = int(request.GET.get("budget", 50))
    except (TypeError, ValueError):
        budget = 50

    # highlight menus
    menus = (
        Menu.objects
        .filter(price__lte=budget)
        .select_related("restaurant")  # ถ้า restaurant เป็น FK
        .order_by("-created_at")[:12]
    )

    ctx = {
        "budget": budget,
        "menus": menus,
        "today_meal_status": None,
        "today_date": None,
    }

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


def login_view(request):
    """
    รองรับ ?next=... เพื่อกลับหน้าที่ผู้ใช้ต้องการหลังล็อกอิน
    """
    next_url = request.GET.get("next") or request.POST.get("next") or ""

    if request.method == "POST":
        form = LoginForm(request, data=request.POST)
        if form.is_valid():
            login(request, form.get_user())
            return redirect(next_url or "home")
        messages.error(request, "ชื่อผู้ใช้หรือรหัสผ่านไม่ถูกต้อง")
    else:
        form = LoginForm(request)

    return render(request, "accounts/login.html", {"form": form, "next": next_url})


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


def logout_view(request):
    logout(request)
    return redirect("home")

# ====================== PROFILE ======================

@login_required
def profile_remove_image_view(request):
    # ปุ่มลบรูปโปรไฟล์ (ต้อง POST เท่านั้น)
    if request.method != "POST":
        return redirect("accounts:profile")

    profile, _ = Profile.objects.get_or_create(user=request.user)

    # ฟิลด์รูปใน models.py ของคุณชื่อ profile_picture
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

        # ถ้าไม่ valid ให้เห็น error
        messages.error(request, "บันทึกไม่สำเร็จ: กรุณาตรวจสอบข้อมูลในฟอร์ม")
    else:
        uform = UserUpdateForm(instance=request.user)
        pform = ProfileUpdateForm(instance=profile)

    # Active plan
    today = timezone.localdate()
    active_plan = None
    active_plan_end = None

    plan_id = request.session.get("active_plan_id")
    if plan_id:
        active_plan = MealPlan.objects.filter(id=plan_id, user=request.user).first()

    if active_plan:
        active_plan_end = active_plan.start_date + timezone.timedelta(days=active_plan.days - 1)

    # ===== ดึงข้อมูลจริง (หาโมเดลแบบไม่ยึดชื่อแอป) =====

    # Community posts: ลองชื่อโมเดลที่พบบ่อย
    PostModel = _find_model_by_names(["Post", "CommunityPost", "Community"])
    my_posts = []
    my_posts_count = 0
    if PostModel:
        uf = _detect_user_field(PostModel)
        if uf:
            qs = PostModel.objects.filter(**{uf: request.user}).order_by("-id")
            my_posts = list(qs[:6])
            my_posts_count = qs.count()

    # Recipes
    RecipeModel = _find_model_by_names(["Recipe", "UserRecipe"])
    my_recipes = []
    my_recipes_count = 0
    if RecipeModel:
        uf = _detect_user_field(RecipeModel)
        if uf:
            qs = RecipeModel.objects.filter(**{uf: request.user}).order_by("-id")
            my_recipes = list(qs[:6])
            my_recipes_count = qs.count()

    # Favorites menus (รองรับหลายแบบ)
    favorite_menus = []
    favorite_menus_count = 0

    # แบบ A: Profile มี ManyToMany ชื่อ favorite_menus
    if hasattr(profile, "favorite_menus"):
        try:
            favorite_menus = list(profile.favorite_menus.all()[:6])
            favorite_menus_count = profile.favorite_menus.count()
        except Exception:
            favorite_menus = []
            favorite_menus_count = 0

    # แบบ B: มีตาราง FavoriteMenu/MenuFavorite/Like/Bookmark ฯลฯ
    if favorite_menus_count == 0:
        FavModel = _find_model_by_names(["FavoriteMenu", "MenuFavorite", "Favorite", "MenuLike", "Bookmark"])
        if FavModel:
            uf = _detect_user_field(FavModel)
            fields = {f.name for f in FavModel._meta.get_fields()}
            if uf and "menu" in fields:
                qs = FavModel.objects.filter(**{uf: request.user}).select_related("menu").order_by("-id")
                favorite_menus_count = qs.count()
                favorite_menus = [x.menu for x in qs[:6] if getattr(x, "menu", None)]

    my_plans_count = MealPlan.objects.filter(user=request.user).count()

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

            "my_posts": my_posts,
            "my_recipes": my_recipes,
            "favorite_menus": favorite_menus,

            "my_posts_count": my_posts_count,
            "my_recipes_count": my_recipes_count,
            "favorite_menus_count": favorite_menus_count,
            "my_plans_count": my_plans_count,
        },
    )
