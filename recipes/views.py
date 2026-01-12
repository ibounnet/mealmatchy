# recipes/views.py
import json
from decimal import Decimal, ROUND_HALF_UP

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
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

import json

def _existing_rows_json_for_recipe(recipe):
    rows = []
    for ri in recipe.recipe_ingredients.select_related("ingredient").all():
        rows.append({
            "ingredient_id": ri.ingredient_id,
            "ingredient_name": ri.ingredient.name,
            "quantity_grams": float(ri.quantity_grams or 0),
            "price_per_gram": float(ri.price_per_gram_snapshot or 0),
            "cost": float(ri.cost_snapshot or 0),
        })
    return json.dumps(rows)


def _save_recipe_ingredients(recipe: Recipe, rows: list):
    """
    rows มาจาก rows_json (snapshot)
    - ลบของเก่า แล้วสร้างใหม่เพื่อความชัวร์
    """
    RecipeIngredient.objects.filter(recipe=recipe).delete()
    created_count = 0

    # โหลด ingredient ทีเดียว
    ids = []
    for r in rows:
        try:
            if r.get("ingredient_id"):
                ids.append(int(r.get("ingredient_id")))
        except Exception:
            pass
    ing_map = {i.id: i for i in Ingredient.objects.filter(id__in=ids)}

    for r in rows:
        try:
            ing_id = int(r.get("ingredient_id"))
        except Exception:
            continue

        grams = _decimal(r.get("quantity_grams") or "0")
        if grams <= 0:
            continue

        ingredient = ing_map.get(ing_id)
        if not ingredient:
            continue

        ppg = r.get("price_per_gram_snapshot")
        if ppg is None:
            ppg_dec = RecipeIngredient.get_price_per_gram_from_ingredient(ingredient)
        else:
            ppg_dec = _decimal(ppg, default="0")

        # recalc ให้ชัวร์เสมอ
        grams_q = grams.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        ppg_q = ppg_dec.quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)
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


def _compute_hidden_cost(recipe: Recipe, setting: UserCookingCostSetting):
    """
    ใช้ในหน้า detail (อิง recipe จริง)
    """
    servings = max(int(recipe.servings or 1), 1)
    basic_hidden = (setting.seasoning_cost_per_serving + setting.overhead_cost_per_serving) * Decimal(servings)
    basic_hidden = basic_hidden.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    if (setting.mode or "basic") == "basic":
        return {
            "mode": "basic",
            "hidden_cost": basic_hidden,
            "note": f"Basic = (เครื่องปรุง {setting.seasoning_cost_per_serving} + แฝง {setting.overhead_cost_per_serving}) x {servings} เสิร์ฟ",
        }

    stove = (recipe.stove_type or "").strip() or setting.default_stove_type
    cook_min = int(recipe.cook_minutes or 0)
    if cook_min <= 0:
        cook_min = int(setting.default_cook_minutes or 0)

    hours = Decimal(str(cook_min)) / Decimal("60")

    if stove == "gas":
        energy_cost = (setting.gas_cost_per_hour * hours).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        energy_note = f"แก๊ส {setting.gas_cost_per_hour} บาท/ชม x {cook_min} นาที"
    else:
        rate = setting.electricity_rate_per_kwh
        watt = setting.electric_power_watt if stove == "electric" else setting.induction_power_watt
        kwh = (Decimal(str(watt)) / Decimal("1000")) * hours
        energy_cost = (rate * kwh).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        energy_note = f"ไฟ {watt}W -> {kwh.quantize(Decimal('0.000'), rounding=ROUND_HALF_UP)} kWh x {rate} บาท/kWh"

    hidden_total = (basic_hidden + energy_cost).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return {
        "mode": "advanced",
        "hidden_cost": hidden_total,
        "note": f"Advanced = (Basic x {servings} เสิร์ฟ) + {energy_note}",
    }


def _compute_hidden_preview(servings, cook_minutes, stove_type, setting: UserCookingCostSetting):
    """
    ใช้ในหน้า add/edit เพื่อส่ง hidden_preview ให้ template
    (ให้ JS เอาไปเป็นค่าเริ่มต้น แล้วค่อยคำนวณ realtime ฝั่งหน้าเว็บ)
    """
    s = max(int(servings or 1), 1)

    seasoning = setting.seasoning_cost_per_serving
    overhead = setting.overhead_cost_per_serving
    basic_per_serving = (seasoning + overhead).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    basic_total = (basic_per_serving * Decimal(s)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    if (setting.mode or "basic") == "basic":
        return {
            "mode": "basic",
            "basic_total": basic_total,
            "energy_cost": Decimal("0.00"),
            "energy_note": "โหมด Basic ไม่คิดค่าไฟ/แก๊ส",
            "hidden_total": basic_total,
            "note": f"Basic = (เครื่องปรุง + แฝงอื่น) x {s} เสิร์ฟ",
        }

    stove = (stove_type or "").strip() or setting.default_stove_type
    cm = int(cook_minutes or 0)
    if cm <= 0:
        cm = int(setting.default_cook_minutes or 0)

    hours = Decimal(str(cm)) / Decimal("60")

    if stove == "gas":
        energy_cost = (setting.gas_cost_per_hour * hours).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        energy_note = f"แก๊ส {setting.gas_cost_per_hour} บาท/ชม x {cm} นาที"
    else:
        rate = setting.electricity_rate_per_kwh
        watt = setting.electric_power_watt if stove == "electric" else setting.induction_power_watt
        kwh = (Decimal(str(watt)) / Decimal("1000")) * hours
        energy_cost = (rate * kwh).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        energy_note = f"ไฟ {watt}W -> {kwh.quantize(Decimal('0.000'), rounding=ROUND_HALF_UP)} kWh x {rate} บาท/kWh"

    hidden_total = (basic_total + energy_cost).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    return {
        "mode": "advanced",
        "basic_total": basic_total,
        "energy_cost": energy_cost,
        "energy_note": energy_note,
        "hidden_total": hidden_total,
        "note": f"Advanced = (Basic x {s} เสิร์ฟ) + Energy",
    }


# =========================================================
# Views (ยึดชื่อเดิมคุณ)
# =========================================================
@login_required
def cost_settings(request):
    setting = _get_or_create_user_setting(request.user)
    next_url = request.GET.get("next") or request.POST.get("next") or ""

    if request.method == "POST":
        form = UserCookingCostSettingForm(request.POST, instance=setting)
        if form.is_valid():
            form.save()
            messages.success(request, "บันทึกการตั้งค่าต้นทุนแฝงเรียบร้อยแล้ว")

            # ถ้ามี next ให้กลับไปหน้าเดิม
            if next_url:
                return redirect(next_url)

            return redirect("recipes:cost_settings")
        messages.error(request, "กรุณาตรวจสอบข้อมูลให้ถูกต้อง")
    else:
        form = UserCookingCostSettingForm(instance=setting)

    return render(request, "recipes/cost_settings.html", {
        "form": form,
        "setting": setting,
        "next": next_url,
    })


@login_required
def recipe_list(request):
    mine_param = (request.GET.get("mine") or "").lower()
    only_mine = mine_param in ("1", "true", "yes", "me")

    qs = Recipe.objects.all().order_by("-created_at")
    if only_mine:
        qs = qs.filter(created_by_id=request.user.id)

    return render(request, "recipes/recipe_list.html", {
        "recipes": qs,
        "only_mine": only_mine,
    })


@login_required
def recipe_detail(request, pk):
    recipe = get_object_or_404(
        Recipe.objects.select_related("created_by").prefetch_related("recipe_ingredients__ingredient"),
        pk=pk
    )

    rows = recipe.recipe_ingredients.all()
    ingredient_cost = recipe.total_cost

    setting = _get_or_create_user_setting(request.user)
    hidden = _compute_hidden_cost(recipe, setting)

    total_cost = (ingredient_cost + hidden["hidden_cost"]).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    servings = max(int(recipe.servings or 1), 1)
    per_serving = (total_cost / Decimal(servings)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    cost_breakdown = {
        "ingredient_cost": ingredient_cost,
        "hidden_cost": hidden["hidden_cost"],
        "total_cost": total_cost,
        "per_serving": per_serving,
        "mode": hidden["mode"],
        "note": hidden["note"],
    }

    return render(request, "recipes/recipe_detail.html", {
        "recipe": recipe,
        "rows": rows,
        "total_cost": ingredient_cost,      # ของเดิม (วัตถุดิบล้วน)
        "cost_breakdown": cost_breakdown,   # ใหม่: hybrid breakdown
    })


@login_required
def add_recipe(request):
    setting = _get_or_create_user_setting(request.user)

    if request.method == "POST":
        form = RecipeForm(request.POST, request.FILES)
        if form.is_valid():
            recipe = form.save(commit=False)
            recipe.created_by = request.user

            # สำคัญ: "" => None เพื่อ fallback
            stove = (form.cleaned_data.get("stove_type") or "").strip()
            recipe.stove_type = stove or None

            recipe.save()

            rows = _parse_rows_json(request.POST.get("rows_json", "[]"))
            created_links = _save_recipe_ingredients(recipe, rows)

            if created_links == 0:
                recipe.delete()
                messages.error(request, "กรุณาเพิ่มวัตถุดิบอย่างน้อย 1 รายการก่อนบันทึกสูตร")
                return redirect("recipes:add")

            messages.success(request, "เพิ่มสูตรอาหารเรียบร้อยแล้ว")
            return redirect("recipes:detail", recipe.id)

        messages.error(request, "กรุณาตรวจสอบข้อมูลให้ถูกต้อง")

        # preview จากค่าที่ผู้ใช้กรอกตอน error
        hidden_preview = _compute_hidden_preview(
            servings=request.POST.get("servings") or 1,
            cook_minutes=request.POST.get("cook_minutes") or 0,
            stove_type=request.POST.get("stove_type") or "",
            setting=setting,
        )
    else:
        form = RecipeForm()
        hidden_preview = _compute_hidden_preview(
            servings=1,
            cook_minutes=0,
            stove_type="",
            setting=setting,
        )

    ingredients = Ingredient.objects.all().order_by("name")
    return render(request, "recipes/add_recipe.html", {
        "form": form,
        "ingredients": ingredients,
        "title": "เพิ่มสูตรอาหาร",
        "submit_text": "บันทึกสูตรอาหาร",
        "setting": setting,
        "hidden_preview": hidden_preview,     # ✅ ให้ template ใช้ค่าเริ่มต้น
        "next": request.get_full_path(),
    })


@login_required
def edit_recipe(request, pk):
    recipe = get_object_or_404(Recipe, pk=pk)
    setting = _get_or_create_user_setting(request.user)

    if recipe.created_by_id != request.user.id and not request.user.is_staff:
        messages.error(request, "คุณไม่มีสิทธิ์แก้ไขสูตรนี้")
        return redirect("recipes:detail", pk)

    if request.method == "POST":
        form = RecipeForm(request.POST, request.FILES, instance=recipe)
        rows = _parse_rows_json(request.POST.get("rows_json", ""))

        if not rows:
            messages.error(request, "ต้องมีวัตถุดิบอย่างน้อย 1 รายการก่อนบันทึก")
        elif form.is_valid():
            recipe = form.save(commit=False)
            stove = (form.cleaned_data.get("stove_type") or "").strip()
            recipe.stove_type = stove or None
            recipe.save()

            _save_recipe_ingredients(recipe, rows)
            messages.success(request, "อัปเดตสูตรอาหารเรียบร้อยแล้ว")
            return redirect("recipes:detail", pk)
        else:
            messages.error(request, "กรุณาตรวจสอบข้อมูลให้ถูกต้อง")

        # ✅ สำคัญ: ถ้า POST แล้ว error ต้องส่งของเดิมกลับด้วย
        existing_rows_json = request.POST.get("rows_json") or _existing_rows_json_for_recipe(recipe)

    else:
        form = RecipeForm(instance=recipe, initial={"stove_type": recipe.stove_type or ""})
        # ✅ สำคัญ: GET edit ต้องส่งของเดิม
        existing_rows_json = _existing_rows_json_for_recipe(recipe)

    ingredients = Ingredient.objects.all().order_by("name")

    hidden_preview = _compute_hidden_preview(
        servings=recipe.servings or 1,
        cook_minutes=recipe.cook_minutes or 0,
        stove_type=recipe.stove_type or "",
        setting=setting,
    )

    return render(request, "recipes/add_recipe.html", {
        "form": form,
        "title": "แก้ไขสูตรอาหาร",
        "submit_text": "บันทึกการเปลี่ยนแปลง",
        "ingredients": ingredients,
        "existing_rows_json": existing_rows_json,   # ✅ key นี้แหละ
        "setting": setting,
        "hidden_preview": hidden_preview,
        "next": request.get_full_path(),
    })

@login_required
def delete_recipe(request, pk):
    base_qs = Recipe.objects.select_related("created_by")
    qs = base_qs if request.user.is_staff else base_qs.filter(created_by=request.user)
    recipe = get_object_or_404(qs, pk=pk)

    if request.method == "POST":
        recipe.delete()
        messages.success(request, "ลบสูตรอาหารเรียบร้อยแล้ว")
        return redirect("recipes:list")

    return render(request, "recipes/delete_recipe.html", {"recipe": recipe})
