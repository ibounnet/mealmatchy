from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.utils.http import url_has_allowed_host_and_scheme

from restaurants.models import Restaurant
from .models import Menu
from .forms import MenuForm
from .utils import filter_by_plan


# ============================
# เมนูฝั่งผู้ใช้ทั่วไป
# ============================

@login_required
def menu_list(request):
    qs = Menu.objects.all().order_by('-created_at')

    # ถ้ามี plan ใน session ให้กรอง
    plan = request.session.get('plan')
    qs = filter_by_plan(qs, plan)

    # ถ้ามี budget ใน query ให้กรองราคาไม่เกิน
    budget = request.GET.get('budget') or (plan and plan.get('budget'))
    if budget and str(budget).isdigit():
        qs = qs.filter(price__lte=int(budget))

    return render(request, 'menus/menu_list.html', {
        'menus': qs,
        'budget': budget or '',
        'plan': plan or {},
    })


@login_required
def add_menu(request):
    if request.method == 'POST':
        form = MenuForm(request.POST, request.FILES)
        if form.is_valid():
            menu = form.save(commit=False)
            menu.created_by = request.user
            menu.status = Menu.Status.PENDING
            menu.save()
            messages.success(request, "เพิ่มเมนูสำเร็จ รอแอดมินอนุมัติ")
            return redirect('menus:menu_list')
        else:
            messages.error(request, "ข้อมูลไม่ถูกต้อง โปรดตรวจสอบอีกครั้ง")
    else:
        form = MenuForm()
    return render(request, 'menus/add_menu.html', {'form': form})


@login_required
def edit_menu(request, pk):
    menu = get_object_or_404(Menu, pk=pk)
    if not request.user.is_staff and menu.created_by_id != request.user.id:
        messages.error(request, 'คุณไม่มีสิทธิ์แก้ไขเมนูนี้')
        return redirect('menus:menu_list')

    if request.method == 'POST':
        form = MenuForm(request.POST, request.FILES, instance=menu)
        if form.is_valid():
            obj = form.save(commit=False)
            # ถ้า user แก้เมนูของตัวเองและเมนูยังไม่อนุมัติ → กลับไป PENDING
            if not request.user.is_staff and menu.status != Menu.Status.APPROVED:
                obj.status = Menu.Status.PENDING
                obj.approved_by = None
                obj.approved_at = None
            obj.save()
            messages.success(request, 'อัปเดตเมนูเรียบร้อยแล้ว')
            return redirect('menus:menu_list')
        messages.error(request, 'แก้ไขไม่สำเร็จ กรุณาตรวจสอบข้อมูล')
    else:
        form = MenuForm(instance=menu)
    return render(request, 'menus/edit_menu.html', {'form': form, 'menu': menu})


@login_required
def delete_menu(request, pk):
    menu = get_object_or_404(Menu, pk=pk)
    if not request.user.is_staff and menu.created_by_id != request.user.id:
        messages.error(request, 'คุณไม่มีสิทธิ์ลบเมนูนี้')
        return redirect('menus:menu_list')

    if request.method == 'POST':
        menu.delete()
        messages.success(request, 'ลบเมนูเรียบร้อยแล้ว')
        return redirect('menus:menu_list')
    return render(request, 'menus/delete_menu.html', {'menu': menu})


# menus/views.py (มีแล้ว)
@login_required
def add_menu_to_restaurant(request, pk):
    restaurant = get_object_or_404(Restaurant, pk=pk, is_active=True)
    if request.method == 'POST':
        form = MenuForm(request.POST, request.FILES)
        if form.is_valid():
            m = form.save(commit=False)
            m.restaurant = restaurant
            m.restaurant_name = restaurant.name
            m.created_by = request.user
            if request.user.is_staff:
                m.status = Menu.Status.APPROVED
                m.approved_by = request.user
                m.approved_at = timezone.now()
                msg = 'เพิ่มเมนูสำเร็จ (อนุมัติทันที)'
            else:
                m.status = Menu.Status.PENDING
                msg = 'ส่งเมนูเรียบร้อย รอแอดมินอนุมัติ'
            m.save()
            messages.success(request, msg)
            return redirect('restaurants:restaurant_detail', pk=restaurant.pk)
    else:
        form = MenuForm()
    return render(
        request,
        'menus/add_menu_to_restaurant.html',
        {'form': form, 'restaurant': restaurant}
    )


# ============================
# เมนูฝั่งแอดมิน
# ============================

@staff_member_required
@require_POST
def approve_menu(request, pk):
    print("METHOD = ", request.method)  # debug
    menu = get_object_or_404(Menu, pk=pk)
    menu.status = Menu.Status.APPROVED
    menu.approved_by = request.user
    menu.approved_at = timezone.now()
    menu.save(update_fields=['status', 'approved_by', 'approved_at'])
    messages.success(request, f"อนุมัติเมนู '{menu.name}' เรียบร้อยแล้ว")
    return redirect('menus:admin_menu_list')


@staff_member_required
@require_POST
def reject_menu(request, pk):
    menu = get_object_or_404(Menu, pk=pk)
    menu.status = Menu.Status.REJECTED
    menu.approved_by = request.user
    menu.approved_at = timezone.now()
    menu.save(update_fields=['status', 'approved_by', 'approved_at'])
    messages.warning(request, f"ปฏิเสธเมนู '{menu.name}' เรียบร้อยแล้ว")

    next_url = request.POST.get('next')
    if next_url and url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}):
        return redirect(next_url)
    return redirect('menus:admin_menu_list')


@staff_member_required
def admin_menu_list(request):
    qs = Menu.objects.all().select_related('restaurant', 'created_by').order_by('-created_at')
    status = (request.GET.get('status') or '').upper()
    q = (request.GET.get('q') or '').strip()

    if status in dict(Menu.Status.choices):
        qs = qs.filter(status=status)
    if q:
        qs = qs.filter(
            Q(name__icontains=q) |
            Q(description__icontains=q) |
            Q(restaurant__name__icontains=q)
        )

    menus = Paginator(qs, 20).get_page(request.GET.get('page', 1))
    return render(request, 'menus/admin_menu_list.html', {
    'menus': menus,
    'q': q,
    'status': status,
    'Menu': Menu,  # เพิ่มบรรทัดนี้
})

@staff_member_required
def admin_edit_menu(request, pk):
    menu = get_object_or_404(Menu, pk=pk)
    if request.method == 'POST':
        form = MenuForm(request.POST, request.FILES, instance=menu)
        if form.is_valid():
            form.save()
            messages.success(request, 'อัปเดตเมนู (แอดมิน) เรียบร้อยแล้ว')
            return redirect('menus:admin_menu_list')
        messages.error(request, 'แก้ไขไม่สำเร็จ กรุณาตรวจสอบข้อมูล')
    else:
        form = MenuForm(instance=menu)
    return render(request, 'menus/admin_edit_menu.html', {'form': form, 'menu': menu})


@staff_member_required
def admin_delete_menu(request, pk):
    menu = get_object_or_404(Menu, pk=pk)
    if request.method == 'POST':
        menu.delete()
        messages.success(request, f"ลบเมนู '{menu.name}' เรียบร้อยแล้ว")
        return redirect('menus:admin_menu_list')
    return render(request, 'menus/admin_delete_menu.html', {'menu': menu})
