# menus/views.py
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from menus.forms import MenuForm

from .models import Menu, Ingredient
from restaurants.models import Restaurant


# =========================
# USER PAGES
# =========================

def menu_list(request):
    """หน้าเมนูรวม
    - ทุกคนเห็น: เมนูที่อนุมัติแล้ว (APPROVED)
    - ถ้าล็อกอิน: เห็น "เมนูของฉัน" เพิ่ม (ทุกสถานะ)
    """
    approved = Menu.objects.filter(status=Menu.Status.APPROVED).order_by("-created_at")

    my_menus = Menu.objects.none()
    if request.user.is_authenticated:
        my_menus = Menu.objects.filter(created_by=request.user).order_by("-created_at")

    return render(request, "menus/menu_list.html", {"menus": approved, "my_menus": my_menus})


def menu_detail(request, pk):
    """หน้ารายละเอียดเมนู
    - ไม่ล็อกอิน: ดูได้เฉพาะ APPROVED
    - ล็อกอิน:
        * staff/admin หรือเจ้าของเมนู -> ดูได้ทุกสถานะ
        * user ทั่วไป -> ดูได้เฉพาะ APPROVED
    """
    m = get_object_or_404(Menu, pk=pk)

    if not request.user.is_authenticated:
        # ผู้ใช้ทั่วไป (ไม่ล็อกอิน)
        if m.status != Menu.Status.APPROVED:
            return redirect("menus:menu_list")
    else:
        if not (request.user.is_staff or request.user.is_superuser or m.created_by == request.user):
            if m.status != Menu.Status.APPROVED:
                return redirect("menus:menu_list")

    return render(request, "menus/menu_detail.html", {"menu": m})


@login_required
def add_menu(request):
    """
    ผู้ใช้ส่งคำขอเพิ่มเมนู -> status=PENDING, created_by=user
    (ฟอร์มของคุณเดิมอาจใช้ templates/menus/add_menu.html อยู่แล้ว)
    """
    if request.method == "POST":
        restaurant_id = request.POST.get("restaurant")
        restaurant_name = (request.POST.get("restaurant_name") or "").strip()
        name = (request.POST.get("name") or "").strip()
        description = (request.POST.get("description") or "").strip()
        price = request.POST.get("price") or "0"
        image = request.FILES.get("image")

        if not name:
            messages.error(request, "กรุณากรอกชื่อเมนู")
            return render(request, "menus/add_menu.html", {"restaurants": Restaurant.objects.filter(is_active=True)})

        restaurant = None
        if restaurant_id:
            restaurant = Restaurant.objects.filter(pk=restaurant_id, is_active=True).first()
            if restaurant and not restaurant_name:
                restaurant_name = restaurant.name

        m = Menu.objects.create(
            restaurant=restaurant,
            restaurant_name=restaurant_name,
            name=name,
            description=description,
            price=price,
            image=image,
            status=Menu.Status.PENDING,
            created_by=request.user,
        )

        # ingredients (optional): รับเป็นชื่อๆคั่นด้วย comma ก็ได้
        # แต่คุณทำ ManyToMany แล้ว ถ้ายังไม่มี UI ก็ข้ามได้
        messages.success(request, "ส่งคำขอเพิ่มเมนูแล้ว รอแอดมินตรวจสอบ")
        return redirect("menus:menu_list")

    return render(request, "menus/add_menu.html", {"restaurants": Restaurant.objects.filter(is_active=True)})


@login_required
def edit_menu(request, pk):
    """
    ให้เจ้าของเมนูแก้ได้ (หรือ staff ก็แก้ได้)
    """
    m = get_object_or_404(Menu, pk=pk)
    if not (request.user.is_staff or request.user.is_superuser or m.created_by == request.user):
        messages.error(request, "คุณไม่มีสิทธิ์แก้ไขเมนูนี้")
        return redirect("menus:menu_list")

    if request.method == "POST":
        m.name = (request.POST.get("name") or "").strip()
        m.description = (request.POST.get("description") or "").strip()
        m.price = request.POST.get("price") or "0"

        restaurant_id = request.POST.get("restaurant")
        restaurant_name = (request.POST.get("restaurant_name") or "").strip()

        if restaurant_id:
            m.restaurant = Restaurant.objects.filter(pk=restaurant_id, is_active=True).first()
            if m.restaurant and not restaurant_name:
                restaurant_name = m.restaurant.name
        m.restaurant_name = restaurant_name

        if "image" in request.FILES:
            m.image = request.FILES["image"]

        if not m.name:
            messages.error(request, "กรุณากรอกชื่อเมนู")
            return render(
                request,
                "menus/edit_menu.html",
                {"menu": m, "restaurants": Restaurant.objects.filter(is_active=True), "ingredients": Ingredient.objects.all()},
            )

        # ถ้าผู้ใช้แก้เมนูหลังจากโดน reject อาจอยากให้กลับไป pending:
        # m.status = Menu.Status.PENDING

        m.save()
        messages.success(request, "แก้ไขเมนูเรียบร้อยแล้ว")
        return redirect("menus:menu_list")

    return render(
        request,
        "menus/edit_menu.html",
        {"menu": m, "restaurants": Restaurant.objects.filter(is_active=True), "ingredients": Ingredient.objects.all()},
    )


@login_required
@require_POST
def delete_menu(request, pk):
    m = get_object_or_404(Menu, pk=pk)
    if not (request.user.is_staff or request.user.is_superuser or m.created_by == request.user):
        messages.error(request, "คุณไม่มีสิทธิ์ลบเมนูนี้")
        return redirect("menus:menu_list")

    name = m.name
    m.delete()
    messages.success(request, f"ลบเมนู '{name}' แล้ว")
    return redirect("menus:menu_list")


@login_required
def add_menu_to_restaurant(request, pk):
    """
    เพิ่มเมนูให้ร้านโดยตรง (ถ้าคุณใช้งาน)
    pk = restaurant id
    """
    r = get_object_or_404(Restaurant, pk=pk, is_active=True)

    if request.method == "POST":
        name = (request.POST.get("name") or "").strip()
        description = (request.POST.get("description") or "").strip()
        price = request.POST.get("price") or "0"
        image = request.FILES.get("image")

        if not name:
            messages.error(request, "กรุณากรอกชื่อเมนู")
            return render(request, "menus/add_menu_to_restaurant.html", {"restaurant": r})

        Menu.objects.create(
            restaurant=r,
            restaurant_name=r.name,
            name=name,
            description=description,
            price=price,
            image=image,
            status=Menu.Status.PENDING,  # ให้เป็นคำขอ
            created_by=request.user,
        )

        messages.success(request, "ส่งคำขอเพิ่มเมนูเข้าร้านแล้ว")
        return redirect("restaurants:restaurant_detail", pk=r.pk)

    return render(request, "menus/add_menu_to_restaurant.html", {"restaurant": r})


# =========================
# ADMIN PAGES (MENUS)
# =========================

@staff_member_required
def admin_menu_list(request):
    """
    status filter: all / pending / approved / rejected
    """
    status = (request.GET.get("status") or "pending").lower()

    qs = Menu.objects.select_related("restaurant", "approved_by", "created_by").order_by("-created_at")
    if status == "pending":
        qs = qs.filter(status=Menu.Status.PENDING)
    elif status == "approved":
        qs = qs.filter(status=Menu.Status.APPROVED)
    elif status == "rejected":
        qs = qs.filter(status=Menu.Status.REJECTED)

    return render(request, "menus/admin_menu_list.html", {"menus": qs, "active_tab": status})

@staff_member_required
def admin_edit_menu(request, pk):
    m = get_object_or_404(Menu, pk=pk)

    if request.method == "POST":
        # ✅ ฟอร์มใช้แก้ name/description/price/image
        form = MenuForm(request.POST, request.FILES, instance=m)

        # ✅ ค่าที่อยู่นอกฟอร์ม: ร้าน (เลือก/พิมพ์เอง)
        restaurant_id = (request.POST.get("restaurant") or "").strip()
        restaurant_name = (request.POST.get("restaurant_name") or "").strip()

        if form.is_valid():
            obj = form.save(commit=False)

            # ถ้าเลือก restaurant (FK) มาก่อน
            if restaurant_id:
                obj.restaurant = Restaurant.objects.filter(pk=restaurant_id, is_active=True).first()
                if obj.restaurant and not restaurant_name:
                    restaurant_name = obj.restaurant.name

            # ถ้าพิมพ์ชื่อร้านเอง -> เก็บใน restaurant_name
            obj.restaurant_name = restaurant_name

            obj.save()
            messages.success(request, "แก้ไขเมนู (Admin) เรียบร้อยแล้ว")
            return redirect("menus:admin_menu_list")

        messages.error(request, "กรุณาตรวจสอบข้อมูลอีกครั้ง")

    else:
        form = MenuForm(instance=m)

    return render(request, "menus/admin_edit_menu.html", {
        "menu": m,
        "form": form,  # ✅ สำคัญ: ให้ template ใช้
        "restaurants": Restaurant.objects.filter(is_active=True),
        "ingredients": Ingredient.objects.all(),
    })

@staff_member_required
@require_POST
def admin_delete_menu(request, pk):
    m = get_object_or_404(Menu, pk=pk)
    name = m.name
    m.delete()
    messages.success(request, f"ลบเมนู '{name}' เรียบร้อยแล้ว")
    return redirect("menus:admin_menu_list")


@staff_member_required
@require_POST
def approve_menu(request, pk):
    m = get_object_or_404(Menu, pk=pk)
    m.status = Menu.Status.APPROVED
    m.approved_by = request.user
    m.approved_at = timezone.now()

    # ถ้า restaurant ถูกเลือกไว้ และ restaurant_name ว่าง ให้เติมชื่อ
    if m.restaurant and not m.restaurant_name:
        m.restaurant_name = m.restaurant.name

    m.save()
    messages.success(request, f"อนุมัติเมนู '{m.name}' เรียบร้อยแล้ว")
    return redirect("menus:admin_menu_list")


@staff_member_required
@require_POST
def reject_menu(request, pk):
    m = get_object_or_404(Menu, pk=pk)
    m.status = Menu.Status.REJECTED
    m.approved_by = request.user
    m.approved_at = timezone.now()
    m.save()
    messages.success(request, f"ปฏิเสธเมนู '{m.name}' เรียบร้อยแล้ว")
    return redirect("menus:admin_menu_list")


# =========================
# ADMIN PAGES (INGREDIENTS)
# =========================

@staff_member_required
def admin_ingredient_list(request):
    qs = Ingredient.objects.all().order_by("name")
    return render(request, "menus/admin_ingredient_list.html", {"ingredients": qs})


@staff_member_required
def admin_ingredient_edit(request, pk):
    ing = get_object_or_404(Ingredient, pk=pk)

    if request.method == "POST":
        ing.name = (request.POST.get("name") or "").strip()
        ing.source = (request.POST.get("source") or "lotus").strip()
        ing.price = request.POST.get("price") or 0
        ing.size_grams = request.POST.get("size_grams") or 0
        ing.price_per_gram = request.POST.get("price_per_gram") or 0

        if not ing.name:
            messages.error(request, "กรุณากรอกชื่อวัตถุดิบ")
            return render(request, "menus/admin_ingredient_edit.html", {"ing": ing})

        ing.save()
        messages.success(request, "แก้ไขวัตถุดิบเรียบร้อยแล้ว")
        return redirect("menus:admin_ingredient_list")

    return render(request, "menus/admin_ingredient_edit.html", {"ing": ing})


@staff_member_required
def admin_ingredient_delete(request, pk):
    ing = get_object_or_404(Ingredient, pk=pk)

    if request.method == "POST":
        ing.delete()
        messages.success(request, "ลบวัตถุดิบเรียบร้อยแล้ว")
        return redirect("menus:admin_ingredient_list")

    return render(request, "menus/admin_ingredient_delete.html", {"ing": ing})