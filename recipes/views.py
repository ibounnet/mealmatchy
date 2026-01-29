# recipes/views.py
import json
from decimal import Decimal, ROUND_HALF_UP

from django.contrib import messages
from django.contrib.auth.decorators import login_required
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
    next_url = request.GET.get("next") or request.POST.get("next") or ""

    if request.method == "POST":
        form = UserCookingCostSettingForm(request.POST, instance=setting)
        if form.is_valid():
            form.save()
            messages.success(request, "บันทึกการตั้งค่าเรียบร้อยแล้ว")
            return redirect(next_url or "recipes:cost_settings")
    else:
        form = UserCookingCostSettingForm(instance=setting)

    return render(request, "recipes/cost_settings.html", {
        "form": form,
        "setting": setting,
        "next": next_url,
    })


@login_required
def recipe_list(request):
    qs = Recipe.objects.order_by("-created_at")
    return render(request, "recipes/recipe_list.html", {"recipes": qs})


@login_required
def recipe_detail(request, pk):
    recipe = get_object_or_404(
        Recipe.objects.prefetch_related("recipe_ingredients__ingredient"), pk=pk
    )

    setting = _get_or_create_user_setting(request.user)
    hidden = _compute_hidden_cost(recipe, setting)

    ingredient_cost = recipe.total_cost
    total_cost = (ingredient_cost + hidden["hidden_cost"]).quantize(Decimal("0.01"))

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
        rows = _parse_rows_json(request.POST.get("rows_json"))

        if form.is_valid() and rows:
            recipe = form.save(commit=False)
            recipe.created_by = request.user
            recipe.stove_type = recipe.stove_type or None
            recipe.save()
            _save_recipe_ingredients(recipe, rows)
            messages.success(request, "เพิ่มสูตรอาหารเรียบร้อยแล้ว")
            return redirect("recipes:detail", recipe.id)

        messages.error(request, "กรุณากรอกข้อมูลให้ครบ")

    else:
        form = RecipeForm()

    return render(request, "recipes/add_recipe.html", {
        "form": form,
        "ingredients": Ingredient.objects.order_by("name"),
        "setting": setting,
        "hidden_preview": _compute_hidden_preview(1, 0, "", setting),
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
