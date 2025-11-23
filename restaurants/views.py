# restaurants/views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.admin.views.decorators import staff_member_required
from django.views.decorators.http import require_POST
from django.contrib import messages
from django.db.models import Q, Case, When, Value, CharField

from .models import Restaurant
from .forms import RestaurantForm
from menus.models import Menu


# ===================== ผู้ใช้ทั่วไป =====================

@login_required
def restaurant_list(request):
    qs = Restaurant.objects.filter(is_active=True).order_by('name')
    q = (request.GET.get('q') or '').strip()
    if q:
        qs = qs.filter(Q(name__icontains=q) | Q(location__icontains=q))
    return render(request, 'restaurants/restaurant_list.html', {
        'restaurants': qs,
        'q': q,
    })


@login_required
def restaurant_detail(request, pk):
    # ผู้ใช้ทั่วไปเห็นเฉพาะร้านที่อนุมัติแล้ว
    restaurant = get_object_or_404(Restaurant, pk=pk, is_active=True)

    # ดึงเมนูของร้านนี้ ตามสิทธิ์ผู้ใช้
    if request.user.is_staff:
        menus_qs = Menu.objects.filter(restaurant=restaurant).order_by('-created_at')
    else:
        menus_qs = (
            Menu.objects
            .filter(restaurant=restaurant)
            .filter(
                Q(status=Menu.Status.APPROVED) |
                Q(created_by=request.user)
            )
            .order_by('-created_at')
        )

    # เตรียมข้อมูล badge สถานะให้ template ใช้งานง่าย
    for m in menus_qs:
        # default: ไม่มี badge (เมนูอนุมัติแล้ว)
        m.status_badge = None
        m.status_badge_class = ""

        if m.status == Menu.Status.PENDING:
            m.status_badge = "รออนุมัติ"
            m.status_badge_class = "bg-yellow-100 text-yellow-700"
        elif m.status == Menu.Status.REJECTED:
            m.status_badge = "ถูกปฏิเสธ"
            m.status_badge_class = "bg-red-100 text-red-700"

    return render(request, 'restaurants/restaurant_detail.html', {
        'restaurant': restaurant,
        'menus': menus_qs,
    })

@login_required
def request_new_restaurant(request):
    """
    ผู้ใช้ส่งคำขอเพิ่มร้านอาหารใหม่
    - is_active=False รอแอดมินอนุมัติ
    """
    if request.method == "POST":
        form = RestaurantForm(request.POST, request.FILES)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.created_by = request.user
            obj.is_active = False  # รอแอดมินอนุมัติ
            obj.save()
            messages.success(request, "ส่งคำขอเพิ่มร้านแล้ว รอผู้ดูแลอนุมัติ")
            return redirect("restaurants:restaurant_list")
        messages.error(request, "กรุณาตรวจสอบข้อมูลให้ถูกต้อง")
    else:
        form = RestaurantForm()

    return render(
        request,
        "restaurants/restaurant_form.html",
        {
            "form": form,
            "title": "ส่งคำขอเพิ่มร้าน",
            "submit_text": "ส่งคำขอ",
            "mode": "request",
        },
    )


# ===================== แอดมิน (หน้าเว็บปกติ ไม่ใช่ Django Admin) =====================


@staff_member_required
def admin_restaurant_list(request):
    """
    หน้าแอดมินสำหรับดู/จัดการรายชื่อร้าน
    สามารถ filter ด้วย ?status=active หรือ ?status=pending ได้
    """
    qs = Restaurant.objects.all().order_by("-created_at")

    status = (request.GET.get("status") or "").lower()
    if status == "active":
        qs = qs.filter(is_active=True)
    elif status == "pending":
        qs = qs.filter(is_active=False)

    return render(
        request,
        "restaurants/admin_restaurant_list.html",
        {
            "restaurants": qs,
            "status": status,
        },
    )


@staff_member_required
def admin_add_restaurant(request):
    if request.method == "POST":
        form = RestaurantForm(request.POST, request.FILES)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.is_active = True  # แอดมินเพิ่ม = เปิดใช้งานทันที
            obj.save()
            messages.success(request, "เพิ่มร้านอาหารเรียบร้อยแล้ว")
            return redirect("restaurants:admin_restaurant_list")
        messages.error(request, "กรุณาตรวจสอบข้อมูลให้ถูกต้อง")
    else:
        form = RestaurantForm()

    return render(
        request,
        "restaurants/admin_add_restaurant.html",
        {
            "form": form,
            "title": "เพิ่มร้านอาหาร (แอดมิน)",
            "submit_text": "บันทึก",
        },
    )


@staff_member_required
def admin_edit_restaurant(request, pk: int):
    r = get_object_or_404(Restaurant, pk=pk)

    if request.method == "POST":
        form = RestaurantForm(request.POST, request.FILES, instance=r)
        if form.is_valid():
            form.save()
            messages.success(request, "แก้ไขร้านอาหารเรียบร้อยแล้ว")
            return redirect("restaurants:admin_restaurant_list")
        messages.error(request, "กรุณาตรวจสอบข้อมูลให้ถูกต้อง")
    else:
        form = RestaurantForm(instance=r)

    return render(
        request,
        "restaurants/admin_edit_restaurant.html",
        {
            "form": form,
            "restaurant": r,
            "title": "แก้ไขร้านอาหาร (แอดมิน)",
            "submit_text": "อัปเดต",
        },
    )


@staff_member_required
def admin_delete_restaurant(request, pk: int):
    r = get_object_or_404(Restaurant, pk=pk)
    if request.method == "POST":
        r.delete()
        messages.success(request, "ลบร้านอาหารเรียบร้อยแล้ว")
        return redirect("restaurants:admin_restaurant_list")
    return render(request, "restaurants/admin_delete_restaurant.html", {"restaurant": r})


@staff_member_required
@require_POST
def admin_approve_restaurant(request, pk: int):
    r = get_object_or_404(Restaurant, pk=pk)
    r.is_active = True
    r.save(update_fields=["is_active"])
    messages.success(request, "อนุมัติร้านอาหารเรียบร้อยแล้ว")
    return redirect("restaurants:admin_restaurant_list")


@staff_member_required
@require_POST
def admin_reject_restaurant(request, pk: int):
    r = get_object_or_404(Restaurant, pk=pk)
    r.is_active = False
    r.save(update_fields=["is_active"])
    messages.success(request, "ปิดการแสดงผล/ปฏิเสธ ร้านอาหารเรียบร้อยแล้ว")
    return redirect("restaurants:admin_restaurant_list")
