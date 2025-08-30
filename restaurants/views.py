from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib import messages
from .models import Restaurant
from .forms import RestaurantForm
from menus.models import Menu
from django.db.models import Q


# ===================== ผู้ใช้ทั่วไป =====================

@login_required
def restaurant_list(request):
    qs = Restaurant.objects.filter(is_active=True).order_by('name')
    q = (request.GET.get('q') or '').strip()
    if q:
        qs = qs.filter(name__icontains=q) | qs.filter(location__icontains=q)
    return render(request, 'restaurants/restaurant_list.html', {'restaurants': qs, 'q': q})

@login_required
def restaurant_detail(request, pk):
    r = get_object_or_404(Restaurant, pk=pk, is_active=True)

    if request.user.is_staff:
        menu_qs = r.menus.all().select_related('created_by').order_by('-created_at')
    else:
        menu_qs = r.menus.filter(
            Q(status=Menu.Status.APPROVED) | Q(created_by=request.user)
        ).select_related('created_by').order_by('-created_at')

    return render(request, 'restaurants/restaurant_detail.html', {
        'restaurant': r,
        'menus': menu_qs,
    })

@login_required
def request_new_restaurant(request):
    if request.method == 'POST':
        form = RestaurantForm(request.POST, request.FILES)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.created_by = request.user
            obj.is_active = False     # รอแอดมินอนุมัติ
            obj.save()
            messages.success(request, 'ส่งคำขอเพิ่มร้านแล้ว รอผู้ดูแลอนุมัติ')
            return redirect('restaurants:restaurant_list')
        messages.error(request, 'กรุณาตรวจสอบข้อมูลให้ถูกต้อง')
    else:
        form = RestaurantForm()
    # ใช้ไฟล์รวมฟอร์มที่คุณมีอยู่แล้ว
    return render(request, 'restaurants/restaurant_form.html', {
        'form': form,
        'title': 'ส่งคำขอเพิ่มร้าน',
        'submit_text': 'ส่งคำขอ',
        'mode': 'request',
    })

# ===================== แอดมิน =====================

@staff_member_required
def admin_restaurant_list(request):
    qs = Restaurant.objects.all().order_by('-created_at')
    status = (request.GET.get('status') or '').lower()
    if status == 'active':
        qs = qs.filter(is_active=True)
    elif status == 'pending':
        qs = qs.filter(is_active=False)
    return render(request, 'restaurants/admin_restaurant_list.html', {
        'restaurants': qs,
        'status': status,
    })

@staff_member_required
def admin_add_restaurant(request):
    if request.method == 'POST':
        form = RestaurantForm(request.POST, request.FILES)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.is_active = True
            obj.save()
            messages.success(request, 'เพิ่มร้านอาหารเรียบร้อยแล้ว')
            return redirect('restaurants:admin_restaurant_list')
        messages.error(request, 'กรุณาตรวจสอบข้อมูลให้ถูกต้อง')
    else:
        form = RestaurantForm()
    return render(request, 'restaurants/admin_add_restaurant.html', {
        'form': form,
        'title': 'เพิ่มร้านอาหาร (แอดมิน)',
        'submit_text': 'บันทึก',
    })

@staff_member_required
def admin_edit_restaurant(request, pk):
    r = get_object_or_404(Restaurant, pk=pk)
    if request.method == 'POST':
        form = RestaurantForm(request.POST, request.FILES, instance=r)
        if form.is_valid():
            form.save()
            messages.success(request, 'แก้ไขร้านอาหารเรียบร้อยแล้ว')
            return redirect('restaurants:admin_restaurant_list')
        messages.error(request, 'กรุณาตรวจสอบข้อมูลให้ถูกต้อง')
    else:
        form = RestaurantForm(instance=r)
    return render(request, 'restaurants/admin_edit_restaurant.html', {
        'form': form,
        'restaurant': r,
        'title': 'แก้ไขร้านอาหาร (แอดมิน)',
        'submit_text': 'อัปเดต',
    })

@staff_member_required
def admin_delete_restaurant(request, pk):
    r = get_object_or_404(Restaurant, pk=pk)
    if request.method == 'POST':
        r.delete()
        messages.success(request, 'ลบร้านอาหารเรียบร้อยแล้ว')
        return redirect('restaurants:admin_restaurant_list')
    return render(request, 'restaurants/admin_delete_restaurant.html', {'restaurant': r})

@staff_member_required
def admin_approve_restaurant(request, pk):
    r = get_object_or_404(Restaurant, pk=pk)
    r.is_active = True
    r.save(update_fields=['is_active'])
    messages.success(request, 'อนุมัติร้านอาหารเรียบร้อยแล้ว')
    return redirect('restaurants:admin_restaurant_list')

@staff_member_required
def admin_reject_restaurant(request, pk):
    r = get_object_or_404(Restaurant, pk=pk)
    r.is_active = False
    r.save(update_fields=['is_active'])
    messages.success(request, 'ปิดการแสดงผล/ปฏิเสธ ร้านอาหารเรียบร้อยแล้ว')
    return redirect('restaurants:admin_restaurant_list')
