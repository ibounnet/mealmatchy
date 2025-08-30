# accounts/views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from .forms import CustomUserCreationForm, UserUpdateForm, ProfileUpdateForm, LoginForm
from .models import Profile

from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from menus.models import Menu  # ต้องมี Model นี้

@login_required
def home_view(request):
    # รับงบจาก query string ?budget=50 (ถ้าไม่ใส่ให้ใช้ 50)
    try:
        budget = int(request.GET.get('budget', 50))
    except ValueError:
        budget = 50

    # แนะนำเมนูที่ราคา <= งบ เรียงล่าสุดก่อน
    menus = Menu.objects.filter(price__lte=budget).order_by('-created_at')[:12]

    return render(request, 'accounts/home.html', {
        'budget': budget,
        'menus': menus,
    })


def register_view(request):
    if request.method == "POST":
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            messages.success(request, "สมัครสมาชิกสำเร็จ! ลองเข้าสู่ระบบได้เลย")
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
            return redirect('home')  # หรือเปลี่ยนเป็น 'menu_list'
        messages.error(request, "ชื่อผู้ใช้หรือรหัสผ่านไม่ถูกต้อง")
    else:
        form = LoginForm(request)
    return render(request, 'accounts/login.html', {'form': form})

def logout_view(request):
    logout(request)
    return redirect('login')


@login_required
def profile_view(request):
    profile, _ = Profile.objects.get_or_create(user=request.user)

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'update':
            uform = UserUpdateForm(request.POST, instance=request.user)
            pform = ProfileUpdateForm(request.POST, request.FILES, instance=profile)
            if uform.is_valid() and pform.is_valid():
                uform.save()
                pform.save()
                messages.success(request, 'อัปเดตโปรไฟล์เรียบร้อยแล้ว')
                return redirect('profile')
            else:
                messages.error(request, 'กรุณาตรวจสอบข้อมูลให้ถูกต้อง')
                return render(request, 'accounts/profile.html', {
                    'uform': uform, 'pform': pform, 'profile': profile
                })

        elif action == 'remove_picture':
            if profile.profile_picture:
                profile.profile_picture.delete(save=False)
                profile.profile_picture = None
                profile.save()
                messages.success(request, 'ลบรูปโปรไฟล์เรียบร้อยแล้ว')
            else:
                messages.info(request, 'ยังไม่มีรูปโปรไฟล์ให้ลบ')
            return redirect('profile')

        elif action == 'delete_profile':
            profile.delete()
            messages.success(request, 'ลบโปรไฟล์เรียบร้อยแล้ว (ระบบจะสร้างใหม่อัตโนมัติเมื่อใช้งานต่อ)')
            return redirect('profile')

    # GET
    uform = UserUpdateForm(instance=request.user)
    pform = ProfileUpdateForm(instance=profile)
    return render(request, 'accounts/profile.html', {'uform': uform, 'pform': pform, 'profile': profile})

# DELETE: ลบเฉพาะ Profile (ไม่ลบ User)
@login_required
def delete_profile(request):
    profile = get_object_or_404(Profile, user=request.user)
    if request.method == 'POST':
        profile.delete()
        messages.success(request, 'ลบโปรไฟล์เรียบร้อยแล้ว (สามารถสร้างใหม่ได้อัตโนมัติเมื่อใช้งานต่อ)')
        return redirect('profile')
    return render(request, 'accounts/profile_confirm_delete.html', {'profile': profile})

# Utility: ลบเฉพาะรูปภาพ
@login_required
def remove_profile_picture(request):
    profile, _ = Profile.objects.get_or_create(user=request.user)
    if profile.profile_picture:
        profile.profile_picture.delete(save=False)
        profile.profile_picture = None
        profile.save()
        messages.success(request, 'ลบรูปโปรไฟล์เรียบร้อยแล้ว')
    return redirect('profile')

# (ออปชัน) READ ทั้งหมด (แอดมินเท่านั้น)
@login_required
def profile_list(request):
    if not (request.user.is_staff or request.user.is_superuser):
        messages.error(request, 'คุณไม่มีสิทธิ์เข้าถึงหน้านี้')
        return redirect('home')
    profiles = Profile.objects.select_related('user').order_by('user__date_joined')
    return render(request, 'accounts/profile_list.html', {'profiles': profiles})
