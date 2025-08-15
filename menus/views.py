from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .models import Menu
from .forms import MenuForm
from django.contrib.admin.views.decorators import staff_member_required
from django.utils.decorators import method_decorator
from django.db.models import Q

@login_required
def menu_list(request):
    if request.user.is_staff:
        menus = Menu.objects.all().order_by('-created_at')
    else:
        menus = Menu.objects.filter(
            Q(created_by=request.user) | Q(created_by__is_staff=True)
        ).order_by('-created_at')
    return render(request, 'menus/menu_list.html', {'menus': menus})

@login_required
def add_menu(request):
    if request.method == 'POST':
        form = MenuForm(request.POST, request.FILES)
        if form.is_valid():
            menu = form.save(commit=False)
            menu.created_by = request.user       # ป้องกัน user_id = NULL
            menu.save()
            messages.success(request, 'บันทึกเมนูเรียบร้อยแล้ว')
            return redirect('menu_list')
        messages.error(request, 'กรุณาตรวจสอบข้อมูลให้ถูกต้อง')
    else:
        form = MenuForm()
    return render(request, 'menus/add_menu.html', {'form': form})

@login_required
def edit_menu(request, pk):
    menu = get_object_or_404(Menu, pk=pk, created_by=request.user)
    if request.method == 'POST':
        form = MenuForm(request.POST, request.FILES, instance=menu)
        if form.is_valid():
            form.save()
            messages.success(request, 'อัปเดตเมนูเรียบร้อยแล้ว')
            return redirect('menu_list')
        messages.error(request, 'แก้ไขไม่สำเร็จ กรุณาตรวจสอบข้อมูล')
    else:
        form = MenuForm(instance=menu)
    return render(request, 'menus/edit_menu.html', {'form': form, 'menu': menu})

@login_required
def delete_menu(request, pk):
    menu = get_object_or_404(Menu, pk=pk, created_by=request.user)
    if request.method == 'POST':
        menu.delete()
        messages.success(request, 'ลบเมนูเรียบร้อยแล้ว')
        return redirect('menu_list')
    return render(request, 'menus/delete_menu.html', {'menu': menu})

@staff_member_required
def admin_menu_list(request):
    # แอดมินเห็นทุกเมนู
    q = request.GET.get("q", "").strip()
    menus = Menu.objects.all().order_by('-created_at')
    if q:
        menus = menus.filter(name__icontains=q)  # ค้นหาจากชื่อเมนู
    context = {"menus": menus, "q": q}
    return render(request, 'menus/admin_menu_list.html', context)

@staff_member_required
def admin_edit_menu(request, pk):
    menu = get_object_or_404(Menu, pk=pk)  # ไม่กรอง created_by
    if request.method == 'POST':
        form = MenuForm(request.POST, request.FILES, instance=menu)
        if form.is_valid():
            form.save()
            messages.success(request, 'อัปเดตเมนู (แอดมิน) เรียบร้อยแล้ว')
            return redirect('admin_menu_list')
        messages.error(request, 'แก้ไขไม่สำเร็จ กรุณาตรวจสอบข้อมูล')
    else:
        form = MenuForm(instance=menu)
    return render(request, 'menus/admin_edit_menu.html', {'form': form, 'menu': menu})

@staff_member_required
def admin_delete_menu(request, pk):
    menu = get_object_or_404(Menu, pk=pk)
    if request.method == 'POST':
        menu.delete()
        messages.success(request, 'ลบเมนู (แอดมิน) เรียบร้อยแล้ว')
        return redirect('admin_menu_list')
    return render(request, 'menus/admin_delete_menu.html', {'menu': menu})