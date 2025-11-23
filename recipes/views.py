# recipes/views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required

from .models import Recipe
from .forms import RecipeForm


@login_required
def recipe_list(request):
    """
    ถ้า query string มี ?mine=1 หรือ mine=true ให้แสดงเฉพาะสูตรของ user คนนั้น
    เช่น /recipes/?mine=1
    """
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
def my_recipe_list(request):
    """
    หน้ารวมสูตรอาหารของ user คนปัจจุบันเท่านั้น (สูตรของฉัน)
    """
    recipes = Recipe.objects.filter(created_by=request.user).order_by('-created_at')
    scope = 'mine'

    return render(request, "recipes/recipe_list.html", {
        "recipes": recipes,
        "scope": scope,
    })


@login_required
def recipe_detail(request, pk):
    recipe = get_object_or_404(Recipe, pk=pk)
    return render(request, "recipes/recipe_detail.html", {
        "recipe": recipe,
    })


@login_required
def add_recipe(request):
    if request.method == "POST":
        form = RecipeForm(request.POST, request.FILES)
        if form.is_valid():
            recipe = form.save(commit=False)
            recipe.created_by = request.user
            recipe.save()
            messages.success(request, "เพิ่มสูตรอาหารเรียบร้อยแล้ว")
            return redirect("recipes:detail", recipe.id)
        else:
            messages.error(request, "กรุณาตรวจสอบข้อมูลให้ถูกต้อง")
    else:
        form = RecipeForm()

    return render(request, "recipes/add_recipe.html", {
        "form": form,
        "title": "เพิ่มสูตรอาหาร",
        "submit_text": "บันทึกสูตรอาหาร",
    })


@login_required
def edit_recipe(request, pk):
    recipe = get_object_or_404(Recipe, pk=pk)
    if recipe.created_by_id != request.user.id and not request.user.is_staff:
        messages.error(request, "คุณไม่มีสิทธิ์แก้ไขสูตรนี้")
        return redirect("recipes:detail", pk)

    if request.method == "POST":
        form = RecipeForm(request.POST, request.FILES, instance=recipe)
        if form.is_valid():
            form.save()
            messages.success(request, "อัปเดตสูตรอาหารเรียบร้อยแล้ว")
            return redirect("recipes:detail", pk)
        else:
            messages.error(request, "กรุณาตรวจสอบข้อมูลให้ถูกต้อง")
    else:
        form = RecipeForm(instance=recipe)

    return render(request, "recipes/add_recipe.html", {
        "form": form,
        "title": "แก้ไขสูตรอาหาร",
        "submit_text": "บันทึกการเปลี่ยนแปลง",
    })


@login_required
def delete_recipe(request, pk):
    """
    ลบสูตรอาหาร:
    - staff ลบได้ทุกอัน
    - user ลบได้เฉพาะของตนเอง
    """
    base_qs = Recipe.objects.select_related("created_by")
    qs = base_qs if request.user.is_staff else base_qs.filter(created_by=request.user)
    recipe = get_object_or_404(qs, pk=pk)

    if request.method == "POST":
        recipe.delete()
        messages.success(request, "ลบสูตรอาหารเรียบร้อยแล้ว")
        return redirect("recipes:list")

    return render(request, "recipes/delete_recipe.html", {"recipe": recipe})
