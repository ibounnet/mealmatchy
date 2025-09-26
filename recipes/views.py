from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q
from .models import Recipe
from .forms import RecipeForm


@login_required
def recipe_list(request):
    """
    แสดงรายการสูตรอาหาร:
    - staff เห็นทั้งหมด
    - user เห็นของตนเอง + ที่ staff สร้าง
    """
    if request.user.is_staff:
        recipes = Recipe.objects.all()
    else:
        recipes = Recipe.objects.filter(
            Q(created_by=request.user) | Q(created_by__is_staff=True)
        )
    recipes = recipes.order_by('-created_at')
    return render(request, 'recipes/recipe_list.html', {'recipes': recipes})


@login_required
def add_recipe(request):
    """เพิ่มสูตรอาหารใหม่"""
    if request.method == 'POST':
        form = RecipeForm(request.POST, request.FILES)
        if form.is_valid():
            recipe = form.save(commit=False)
            recipe.created_by = request.user
            recipe.save()
            messages.success(request, 'บันทึกสูตรอาหารเรียบร้อยแล้ว')
            return redirect('recipes:list')
        messages.error(request, 'กรุณาตรวจสอบข้อมูลให้ถูกต้อง')
    else:
        form = RecipeForm()
    return render(request, 'recipes/add_recipe.html', {'form': form})


@login_required
def edit_recipe(request, pk):
    """
    แก้ไขสูตรอาหาร:
    - staff แก้ไขได้ทุกอัน
    - user แก้ไขได้เฉพาะของตนเอง
    """
    qs = Recipe.objects.all() if request.user.is_staff else Recipe.objects.filter(created_by=request.user)
    recipe = get_object_or_404(qs, pk=pk)

    if request.method == 'POST':
        form = RecipeForm(request.POST, request.FILES, instance=recipe)
        if form.is_valid():
            form.save()
            messages.success(request, 'อัปเดตสูตรอาหารเรียบร้อยแล้ว')
            return redirect('recipes:list')
        messages.error(request, 'แก้ไขไม่สำเร็จ กรุณาตรวจสอบข้อมูล')
    else:
        form = RecipeForm(instance=recipe)

    return render(request, 'recipes/edit_recipe.html', {'form': form, 'recipe': recipe})


@login_required
def delete_recipe(request, pk):
    """
    ลบสูตรอาหาร:
    - staff ลบได้ทุกอัน
    - user ลบได้เฉพาะของตนเอง
    """
    qs = Recipe.objects.all() if request.user.is_staff else Recipe.objects.filter(created_by=request.user)
    recipe = get_object_or_404(qs, pk=pk)

    if request.method == 'POST':
        recipe.delete()
        messages.success(request, 'ลบสูตรอาหารเรียบร้อยแล้ว')
        return redirect('recipes:list')

    return render(request, 'recipes/delete_recipe.html', {'recipe': recipe})
