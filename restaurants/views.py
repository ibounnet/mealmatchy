# restaurants/views.py
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .models import Restaurant


# ==========================
# USER PAGES (ของเดิมคุณมีอยู่แล้ว)
# ==========================
def restaurant_list(request):
    qs = Restaurant.objects.filter(is_active=True).order_by("-created_at")
    return render(request, "restaurants/restaurant_list.html", {"restaurants": qs})


def restaurant_detail(request, pk):
    r = get_object_or_404(Restaurant, pk=pk, is_active=True)

    # ✅ เมนูของร้าน: รองรับทั้ง
    # 1) เมนูที่ผูก FK restaurant
    # 2) เมนูเก่าที่ restaurant เป็น NULL แต่มี restaurant_name เก็บชื่อร้านไว้
    from menus.models import Menu  # import ในฟังก์ชันเพื่อลด circular import

    menus_qs = (
        Menu.objects.filter(
            Q(restaurant=r) |
            (Q(restaurant__isnull=True) & Q(restaurant_name__icontains=r.name))
        )
        .select_related("restaurant", "created_by")
        .order_by("-created_at")
        .distinct()
    )

    # ✅ คุมสิทธิ์การมองเห็น
    if not request.user.is_authenticated:
        menus_qs = menus_qs.filter(status=Menu.Status.APPROVED)
    else:
        if not (request.user.is_staff or request.user.is_superuser):
            menus_qs = menus_qs.filter(Q(status=Menu.Status.APPROVED) | Q(created_by=request.user))

    return render(request, "restaurants/restaurant_detail.html", {"restaurant": r, "menus": menus_qs})

def request_new_restaurant(request):
    """
    คำขอเพิ่มร้าน: สร้าง Restaurant โดย is_active=False และ created_by=request.user (ถ้า login)
    คุณมี template/restaurant_form.html อยู่แล้ว
    """
    if request.method == "POST":
        name = (request.POST.get("name") or "").strip()
        description = (request.POST.get("description") or "").strip()
        location = (request.POST.get("location") or "").strip()
        image = request.FILES.get("image")

        if not name:
            messages.error(request, "กรุณากรอกชื่อร้าน")
            return render(request, "restaurants/restaurant_form.html")

        if Restaurant.objects.filter(name=name).exists():
            messages.error(request, "ชื่อร้านนี้มีอยู่แล้ว")
            return render(request, "restaurants/restaurant_form.html")

        r = Restaurant.objects.create(
            name=name,
            description=description,
            location=location,
            image=image,
            is_active=False,
            created_by=request.user if request.user.is_authenticated else None,
        )
        messages.success(request, "ส่งคำขอเพิ่มร้านอาหารแล้ว รอแอดมินตรวจสอบ")
        return redirect("restaurants:restaurant_list")

    return render(request, "restaurants/restaurant_form.html")


# ==========================
# ADMIN PAGES
# ==========================
@staff_member_required
def admin_restaurant_list(request):
    status = (request.GET.get("status") or "all").lower()

    qs = Restaurant.objects.all().order_by("-created_at")

    if status == "pending":
        qs = qs.filter(is_active=False)
    elif status == "approved":
        qs = qs.filter(is_active=True)

    # decorate ให้ template ใช้ง่าย
    restaurants = []
    for r in qs:
        r._mm_status = "approved" if r.is_active else "pending"
        r._mm_requester = r.created_by.username if r.created_by else "-"
        restaurants.append(r)

    return render(
        request,
        "restaurants/admin_restaurant_list.html",
        {"restaurants": restaurants, "active_tab": status},
    )


@staff_member_required
@require_POST
def admin_approve_restaurant(request, pk):
    r = get_object_or_404(Restaurant, pk=pk)
    r.is_active = True
    r.save(update_fields=["is_active"])
    messages.success(request, f"อนุมัติร้าน '{r.name}' เรียบร้อยแล้ว")
    return redirect("restaurants:admin_restaurant_list")


@staff_member_required
@require_POST
def admin_reject_restaurant(request, pk):
    r = get_object_or_404(Restaurant, pk=pk)
    name = r.name
    r.delete()
    messages.success(request, f"ปฏิเสธและลบคำขอร้าน '{name}' เรียบร้อยแล้ว")
    return redirect("restaurants:admin_restaurant_list")


@staff_member_required
def admin_add_restaurant(request):
    """
    เพิ่มร้านโดยแอดมิน: บันทึกเป็น is_active=True
    ใช้ template: restaurants/admin_add_restaurant.html (มีอยู่แล้วตามภาพ)
    """
    if request.method == "POST":
        name = (request.POST.get("name") or "").strip()
        description = (request.POST.get("description") or "").strip()
        location = (request.POST.get("location") or "").strip()
        image = request.FILES.get("image")

        if not name:
            messages.error(request, "กรุณากรอกชื่อร้าน")
            return render(request, "restaurants/admin_add_restaurant.html")

        if Restaurant.objects.filter(name=name).exists():
            messages.error(request, "ชื่อร้านนี้มีอยู่แล้ว")
            return render(request, "restaurants/admin_add_restaurant.html")

        Restaurant.objects.create(
            name=name,
            description=description,
            location=location,
            image=image,
            is_active=True,
            created_by=request.user,
        )
        messages.success(request, "เพิ่มร้านอาหารเรียบร้อยแล้ว")
        return redirect("restaurants:admin_restaurant_list")

    return render(request, "restaurants/admin_add_restaurant.html")


@staff_member_required
def admin_edit_restaurant(request, pk):
    r = get_object_or_404(Restaurant, pk=pk)

    if request.method == "POST":
        r.name = (request.POST.get("name") or "").strip()
        r.description = (request.POST.get("description") or "").strip()
        r.location = (request.POST.get("location") or "").strip()

        if "image" in request.FILES:
            r.image = request.FILES["image"]

        # toggle active ได้จากฟอร์มถ้ามี checkbox
        is_active = request.POST.get("is_active")
        if is_active is not None:
            r.is_active = (is_active == "on")

        if not r.name:
            messages.error(request, "กรุณากรอกชื่อร้าน")
            return render(request, "restaurants/admin_edit_restaurant.html", {"restaurant": r})

        r.save()
        messages.success(request, "แก้ไขร้านอาหารเรียบร้อยแล้ว")
        return redirect("restaurants:admin_restaurant_list")

    return render(request, "restaurants/admin_edit_restaurant.html", {"restaurant": r})


@staff_member_required
@require_POST
def admin_delete_restaurant(request, pk):
    r = get_object_or_404(Restaurant, pk=pk)
    name = r.name
    r.delete()
    messages.success(request, f"ลบร้าน '{name}' เรียบร้อยแล้ว")
    return redirect("restaurants:admin_restaurant_list")
