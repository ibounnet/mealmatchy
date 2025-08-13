from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .models import Menu
from .forms import MenuForm

@login_required
def menu_list(request):
    # แสดงเฉพาะเมนูที่ “ตนเอง” เพิ่ม (ปรับตามต้องการ)
    menus = Menu.objects.filter(created_by=request.user).order_by('-created_at')
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
