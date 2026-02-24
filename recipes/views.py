# recipes/views.py
import json
from decimal import Decimal, ROUND_HALF_UP

from django.core.paginator import Paginator
from django.db.models import Q
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.urls import reverse
from django.shortcuts import render, redirect, get_object_or_404

from menus.models import Ingredient
from .models import Recipe, RecipeIngredient, UserCookingCostSetting
from .forms import RecipeForm, UserCookingCostSettingForm


# =========================================================
# Utils
# =========================================================
def _decimal(x, default="0"):
    try:
        return Decimal(str(x))
    except Exception:
        return Decimal(default)


def _parse_rows_json(rows_json_raw: str):
    if not rows_json_raw:
        return []
    try:
        data = json.loads(rows_json_raw)
        return data if isinstance(data, list) else []
    except Exception:
        return []


def _get_or_create_user_setting(user):
    obj, _ = UserCookingCostSetting.objects.get_or_create(user=user)
    return obj


def _existing_rows_json_for_recipe(recipe):
    """
    ดึงวัตถุดิบเดิมของสูตร → ส่งกลับเป็น JSON
    ใช้ตอน GET edit และตอน POST error
    """
    rows = []
    for ri in recipe.recipe_ingredients.select_related("ingredient").all():
        rows.append({
            "ingredient_id": ri.ingredient_id,
            "ingredient_name": ri.ingredient.name,
            "quantity_grams": float(ri.quantity_grams or 0),
            "price_per_gram_snapshot": float(ri.price_per_gram_snapshot or 0),
            "cost_snapshot": float(ri.cost_snapshot or 0),
        })
    return json.dumps(rows)


def _save_recipe_ingredients(recipe: Recipe, rows: list):
    """
    บันทึกวัตถุดิบ (snapshot)
    - ลบของเก่า
    - คำนวณใหม่ให้ตรงเสมอ
    """
    RecipeIngredient.objects.filter(recipe=recipe).delete()
    created_count = 0

    ids = []
    for r in rows:
        try:
            ids.append(int(r.get("ingredient_id")))
        except Exception:
            pass

    ing_map = {i.id: i for i in Ingredient.objects.filter(id__in=ids)}

    for r in rows:
        try:
            ing_id = int(r.get("ingredient_id"))
        except Exception:
            continue

        grams = _decimal(r.get("quantity_grams"))
        if grams <= 0:
            continue

        ingredient = ing_map.get(ing_id)
        if not ingredient:
            continue

        ppg = _decimal(r.get("price_per_gram_snapshot"))
        grams_q = grams.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        ppg_q = ppg.quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)
        cost_q = (grams_q * ppg_q).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

        RecipeIngredient.objects.create(
            recipe=recipe,
            ingredient=ingredient,
            quantity_grams=grams_q,
            price_per_gram_snapshot=ppg_q,
            cost_snapshot=cost_q,
        )
        created_count += 1

    return created_count


# =========================================================
# Hybrid cost calculation
# =========================================================
def _compute_hidden_cost(recipe: Recipe, setting: UserCookingCostSetting):
    servings = max(int(recipe.servings or 1), 1)

    basic_total = (
        (setting.seasoning_cost_per_serving + setting.overhead_cost_per_serving)
        * Decimal(servings)
    ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    if setting.mode == "basic":
        return {
            "mode": "basic",
            "hidden_cost": basic_total,
            "note": "คำนวณจากค่าเฉลี่ยต่อเสิร์ฟ (Basic)",
        }

    stove = recipe.stove_type or setting.default_stove_type
    cook_min = recipe.cook_minutes or setting.default_cook_minutes
    hours = Decimal(cook_min) / Decimal("60")

    if stove == "gas":
        energy = (setting.gas_cost_per_hour * hours)
        note = f"แก๊ส {setting.gas_cost_per_hour} บาท/ชม × {cook_min} นาที"
    else:
        watt = (
            setting.induction_power_watt
            if stove == "induction"
            else setting.electric_power_watt
        )
        kwh = (Decimal(watt) / Decimal("1000")) * hours
        energy = setting.electricity_rate_per_kwh * kwh
        note = f"ไฟ {watt}W → {kwh:.3f} kWh"

    energy = energy.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return {
        "mode": "advanced",
        "hidden_cost": (basic_total + energy).quantize(Decimal("0.01")),
        "note": f"Advanced = Basic + {note}",
    }


def _compute_hidden_preview(servings, cook_minutes, stove_type, setting):
    s = max(int(servings or 1), 1)

    basic = (
        (setting.seasoning_cost_per_serving + setting.overhead_cost_per_serving)
        * Decimal(s)
    ).quantize(Decimal("0.01"))

    if setting.mode == "basic":
        return {
            "hidden_total": basic,
            "basic_total": basic,
            "energy_cost": Decimal("0.00"),
            "note": "โหมด Basic (ไม่คิดพลังงาน)",
        }

    stove = stove_type or setting.default_stove_type
    cm = cook_minutes or setting.default_cook_minutes
    hours = Decimal(cm) / Decimal("60")

    if stove == "gas":
        energy = setting.gas_cost_per_hour * hours
        note = "แก๊ส"
    else:
        watt = (
            setting.induction_power_watt
            if stove == "induction"
            else setting.electric_power_watt
        )
        energy = setting.electricity_rate_per_kwh * (
            (Decimal(watt) / Decimal("1000")) * hours
        )
        note = "ไฟฟ้า"

    energy = energy.quantize(Decimal("0.01"))
    return {
        "hidden_total": (basic + energy).quantize(Decimal("0.01")),
        "basic_total": basic,
        "energy_cost": energy,
        "note": f"Advanced ({note})",
    }


# =========================================================
# Views
# =========================================================
@login_required
def cost_settings(request):
    setting = _get_or_create_user_setting(request.user)

    # รับ next จาก GET/POST
    next_url = (request.POST.get("next") or request.GET.get("next") or "").strip()

    if request.method == "POST":
        form = UserCookingCostSettingForm(request.POST, instance=setting)
        if form.is_valid():
            form.save()
            messages.success(request, "บันทึกการตั้งค่าเรียบร้อยแล้ว")

            # ✅ อยู่หน้าเดิมหลังบันทึก (แต่พก next ไปด้วย)
            if next_url:
                return redirect(f"{reverse('recipes:cost_settings')}?next={next_url}")
            return redirect("recipes:cost_settings")
        else:
            messages.error(request, "กรุณาตรวจสอบข้อมูลที่กรอก")
    else:
        form = UserCookingCostSettingForm(instance=setting)

    return render(request, "recipes/cost_settings.html", {
        "form": form,
        "setting": setting,
        "next": next_url,
    })

def _cost_per_serving_decimal(recipe: Recipe) -> Decimal:
    servings = max(int(recipe.servings or 1), 1)
    total = (recipe.total_cost or Decimal("0"))
    return (total / Decimal(servings)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)



def recipe_list(request, mine_only=False):
    mine_only = bool(mine_only)

    # ถ้าเข้าหน้า 'สูตรของฉัน' แต่ยังไม่ล็อกอิน ให้ไปหน้าเข้าสู่ระบบ
    if mine_only and not request.user.is_authenticated:
        return redirect('accounts:login')

    q = (request.GET.get("q") or "").strip()
    sort = (request.GET.get("sort") or "new").strip()
    hide_zero = (request.GET.get("hide_zero") or "0").strip()  # "1" = hide

    qs = Recipe.objects.all()

    # ✅ สูตรของฉัน (รองรับชื่อ field ผู้สร้างหลายแบบ)
    if mine_only:
        if hasattr(Recipe, "created_by"):
            qs = qs.filter(created_by=request.user)
        elif hasattr(Recipe, "author"):
            qs = qs.filter(author=request.user)

    # ✅ search
    if q:
        qs = qs.filter(Q(title__icontains=q) | Q(description__icontains=q))

    qs = qs.order_by("-created_at")

    # ✅ build items for template (คำนวณ cost/time)
    items = []
    for r in qs:
        cost_per_serving = _cost_per_serving_decimal(r)

        # ✅ ซ่อนสูตรต้นทุน/เสิร์ฟ = 0 ตามอาจารย์
        if hide_zero == "1" and cost_per_serving <= 0:
            continue

        total_minutes = int((r.prep_minutes or 0) + (r.cook_minutes or 0))
        items.append({
            "recipe": r,
            "cost_per_serving": float(cost_per_serving),
            "total_minutes": total_minutes,
            "servings": int(r.servings or 1),
            "total_cost": float((r.total_cost or Decimal("0")).quantize(Decimal("0.01"))),
        })

    # ✅ sorting (ทำใน python เพราะ item เป็น dict)
    if sort == "old":
        items.sort(key=lambda x: x["recipe"].created_at)
    elif sort == "cost_low":
        items.sort(key=lambda x: (0 if x["cost_per_serving"] > 0 else 1, x["cost_per_serving"]))
    elif sort == "cost_high":
        items.sort(key=lambda x: (0 if x["cost_per_serving"] > 0 else 1, -x["cost_per_serving"]))
    elif sort == "time_low":
        items.sort(key=lambda x: x["total_minutes"])
    elif sort == "time_high":
        items.sort(key=lambda x: -x["total_minutes"])
    else:
        # new
        items.sort(key=lambda x: x["recipe"].created_at, reverse=True)

    # ✅ pagination
    paginator = Paginator(items, 9)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    return render(request, "recipes/recipe_list.html", {
        "mine_only": mine_only,
        "q": q,
        "sort": sort,
        "hide_zero": hide_zero,

        "page_obj": page_obj,
        "paginator": paginator,
        "is_paginated": page_obj.has_other_pages(),
    })




def recipe_detail(request, pk):
    recipe = get_object_or_404(
        Recipe.objects.prefetch_related("recipe_ingredients__ingredient"), pk=pk
    )

    # ✅ ผู้ใช้ทั่วไป (ยังไม่ล็อกอิน) ให้ดูได้แบบ view-only
    #    - ไม่สร้าง setting
    #    - ไม่คำนวณต้นทุนแฝง (แสดงเฉพาะต้นทุนวัตถุดิบที่ snapshot ไว้)
    if not request.user.is_authenticated:
        ingredient_cost = (recipe.total_cost or Decimal("0")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        return render(request, "recipes/recipe_detail.html", {
            "recipe": recipe,
            "rows": recipe.recipe_ingredients.all(),
            "total_cost": ingredient_cost,
            "cost_breakdown": None,
        })

    # ✅ ผู้ใช้ที่ล็อกอิน: คำนวณต้นทุนแบบ Hybrid (วัตถุดิบ + ต้นทุนแฝง)
    setting = _get_or_create_user_setting(request.user)
    hidden = _compute_hidden_cost(recipe, setting)

    ingredient_cost = recipe.total_cost or Decimal("0")
    total_cost = (ingredient_cost + hidden["hidden_cost"]).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    return render(request, "recipes/recipe_detail.html", {
        "recipe": recipe,
        "rows": recipe.recipe_ingredients.all(),
        "cost_breakdown": {
            "ingredient_cost": ingredient_cost,
            "hidden_cost": hidden["hidden_cost"],
            "total_cost": total_cost,
            "mode": hidden["mode"],
            "note": hidden["note"],
        },
    })


@login_required
def add_recipe(request):
    setting = _get_or_create_user_setting(request.user)

    if request.method == "POST":
        form = RecipeForm(request.POST, request.FILES)

        # rows_json มาจาก hidden input ชื่อ rows_json
        rows = _parse_rows_json(request.POST.get("rows_json"))

        if form.is_valid():
            recipe = form.save(commit=False)
            recipe.created_by = request.user

            # ถ้าไม่เลือกเตา ให้เป็น None
            recipe.stove_type = recipe.stove_type or None

            recipe.save()

            # ✅ บันทึกวัตถุดิบแบบตาราง (มีหรือไม่มีได้)
            if rows:
                _save_recipe_ingredients(recipe, rows)

            # ❗ถ้าหนูต้อง "บังคับ" ให้มีวัตถุดิบอย่างน้อย 1 รายการจริง ๆ
            # ให้ย้าย recipe.save() ลงมาหลังเช็ค rows และทำ messages.error แล้ว return render แทน
            # แต่ตอนนี้พี่ทำแบบ "เซฟสูตรได้" เพื่อกันข้อมูล steps/ingredients หายตอนสอบ

            messages.success(request, "เพิ่มสูตรอาหารเรียบร้อยแล้ว")
            return redirect("recipes:detail", recipe.id)

        messages.error(request, "กรุณาตรวจสอบข้อมูลที่กรอกให้ครบถ้วน")

        # ✅ preview ตอน POST ไม่ผ่าน (ดึงค่าจากฟอร์มที่ผู้ใช้กรอก)
        servings = int(request.POST.get("servings") or 1)
        cook_min = int(request.POST.get("cook_minutes") or 0)
        stove = (request.POST.get("stove_type") or "").strip()

        hidden_preview = _compute_hidden_preview(servings, cook_min, stove, setting)

    else:
        form = RecipeForm()
        hidden_preview = _compute_hidden_preview(1, 0, "", setting)

    return render(request, "recipes/add_recipe.html", {
        "form": form,
        "ingredients": Ingredient.objects.order_by("name"),
        "setting": setting,
        "hidden_preview": hidden_preview,
    })


@login_required
def edit_recipe(request, pk):
    recipe = get_object_or_404(Recipe, pk=pk)
    setting = _get_or_create_user_setting(request.user)

    if request.method == "POST":
        form = RecipeForm(request.POST, request.FILES, instance=recipe)
        rows = _parse_rows_json(request.POST.get("rows_json"))

        if form.is_valid() and rows:
            recipe = form.save(commit=False)
            recipe.stove_type = recipe.stove_type or None
            recipe.save()
            _save_recipe_ingredients(recipe, rows)
            messages.success(request, "อัปเดตสูตรเรียบร้อยแล้ว")
            return redirect("recipes:detail", recipe.id)

        existing_rows_json = request.POST.get("rows_json")

    else:
        form = RecipeForm(instance=recipe)
        existing_rows_json = _existing_rows_json_for_recipe(recipe)

    return render(request, "recipes/add_recipe.html", {
        "form": form,
        "ingredients": Ingredient.objects.order_by("name"),
        "existing_rows_json": existing_rows_json,
        "setting": setting,
        "hidden_preview": _compute_hidden_preview(
            recipe.servings, recipe.cook_minutes, recipe.stove_type, setting
        ),
    })


@login_required
def delete_recipe(request, pk):
    recipe = get_object_or_404(Recipe, pk=pk)
    if request.method == "POST":
        recipe.delete()
        return redirect("recipes:list")
    return render(request, "recipes/delete_recipe.html", {"recipe": recipe})

def match_recipes_by_budget(budget: Decimal, recipes, setting):
    """
    คืน list ของสูตรที่อยู่ในงบ หรือใกล้งบ
    """
    matched = []

    for recipe in recipes:
        ingredient_cost = recipe.total_cost
        hidden = _compute_hidden_cost(recipe, setting)
        total_cost = (ingredient_cost + hidden["hidden_cost"]).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )

        diff = budget - total_cost

        if diff >= Decimal("-10"):  # อนุโลมเกินงบไม่เกิน 10 บาท
            matched.append({
                "recipe": recipe,
                "total_cost": total_cost,
                "diff": diff,
                "status": (
                    "ต่ำกว่างบ" if diff >= 0
                    else "ใกล้งบ"
                )
            })

    # เรียงจากถูก → แพง
    matched.sort(key=lambda x: x["total_cost"])
    return matched
