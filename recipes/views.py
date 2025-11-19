from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages

from .models import Recipe
from .forms import RecipeForm


@login_required
def recipe_list(request):
    """
    หน้า 'รวมสูตรอาหาร'
    - ให้ผู้ใช้ทุกคนเห็นสูตรอาหารของทุกคน
    """
    recipes = (
        Recipe.objects
        .select_related("created_by", "created_by__profile")
        .order_by("-created_at")
    )
    return render(request, "recipes/recipe_list.html", {"recipes": recipes})


@login_required
def recipe_detail(request, pk):
    """
    หน้าดูรายละเอียดสูตรอาหาร 1 รายการ
    """
    recipe = get_object_or_404(
        Recipe.objects.select_related("created_by", "created_by__profile"),
        pk=pk,
    )
    return render(request, "recipes/recipe_detail.html", {"recipe": recipe})


@login_required
def add_recipe(request):
    """เพิ่มสูตรอาหารใหม่"""
    if request.method == "POST":
        form = RecipeForm(request.POST, request.FILES)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.created_by = request.user
            obj.save()
            messages.success(request, "บันทึกสูตรอาหารเรียบร้อยแล้ว")
            return redirect("recipes:list")
        messages.error(request, "กรุณาตรวจสอบข้อมูลให้ถูกต้อง")
    else:
        form = RecipeForm()

    return render(request, "recipes/add_recipe.html", {"form": form})


@login_required
def edit_recipe(request, pk):
    """
    แก้ไขสูตรอาหาร:
    - staff แก้ได้ทุกอัน
    - user แก้ได้เฉพาะของตนเอง
    """
    base_qs = Recipe.objects.select_related("created_by")
    qs = base_qs if request.user.is_staff else base_qs.filter(created_by=request.user)
    recipe = get_object_or_404(qs, pk=pk)

    if request.method == "POST":
        form = RecipeForm(request.POST, request.FILES, instance=recipe)
        if form.is_valid():
            form.save()
            messages.success(request, "อัปเดตสูตรอาหารเรียบร้อยแล้ว")
            return redirect("recipes:list")
        messages.error(request, "แก้ไขไม่สำเร็จ กรุณาตรวจสอบข้อมูล")
    else:
        form = RecipeForm(instance=recipe)

    return render(request, "recipes/add_recipe.html", {  # ใช้ template เดียวกับ add
        "form": form,
        "recipe": recipe,
        "is_edit": True,
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
