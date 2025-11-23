# accounts/views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required

from .forms import (
    CustomUserCreationForm,
    UserUpdateForm,
    ProfileUpdateForm,
    LoginForm,
)
from .models import Profile
from menus.models import Menu


# ====================== HOME ======================

def home_view(request):
    """
    หน้าแรก: แสดงปุ่ม 'เริ่มวางแผนมื้ออาหาร', เมนูแนะนำในงบ และกล่องแนะนำ Community
    ใส่งบผ่าน query string ?budget=50 (default = 50)
    """
    try:
        budget = int(request.GET.get('budget', 50))
    except (TypeError, ValueError):
        budget = 50

    menus = (
        Menu.objects.filter(price__lte=budget)
        .order_by('-created_at')[:12]
    )

    return render(request, 'accounts/home.html', {
        'budget': budget,
        'menus': menus,
    })


# ====================== AUTH ======================

def register_view(request):
    if request.method == "POST":
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            messages.success(request, "สมัครสมาชิกสำเร็จ! ลองล็อกอินได้เลย")
            return redirect('login')
        messages.error(request, "กรุณาตรวจสอบข้อมูลให้ถูกต้อง")
    else:
        form = CustomUserCreationForm()
    return render(request, 'accounts/register.html', {'form': form})


def login_view(request):
    if request.method == 'POST':
        form = LoginForm(request, data=request.POST)
        if form.is_valid():
            login(request, form.get_user())
            return redirect('home')   # กลับหน้าแรกหลังล็อกอิน
        messages.error(request, "ชื่อผู้ใช้หรือรหัสผ่านไม่ถูกต้อง")
    else:
        form = LoginForm(request)
    return render(request, 'accounts/login.html', {'form': form})


def logout_view(request):
    logout(request)
    return redirect('login')


# ====================== PROFILE ======================

@login_required
def profile_view(request):
    """
    จัดการโปรไฟล์ผู้ใช้ (ชื่อ-อีเมล + รูปโปรไฟล์)
    """
    profile, _ = Profile.objects.get_or_create(user=request.user)

    if request.method == 'POST':
        uform = UserUpdateForm(request.POST, instance=request.user)
        pform = ProfileUpdateForm(request.POST, request.FILES, instance=profile)
        if uform.is_valid() and pform.is_valid():
            uform.save()
            pform.save()
            messages.success(request, 'อัปเดตโปรไฟล์เรียบร้อยแล้ว')
            return redirect('profile')
        messages.error(request, 'กรุณาตรวจสอบข้อมูลให้ถูกต้อง')
    else:
        uform = UserUpdateForm(instance=request.user)
        pform = ProfileUpdateForm(instance=profile)

    return render(request, 'accounts/profile.html', {
        'uform': uform,
        'pform': pform,
        'profile': profile,
    })
