# accounts/views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from .forms import CustomUserCreationForm, UserUpdateForm, ProfileUpdateForm, LoginForm
from .models import Profile
from menus.models import Menu


# ---------- HOME ----------
@login_required
def home_view(request):
    # อ่านงบจาก query (?budget=50) ค่าเริ่มต้น 50
    try:
        budget = int(request.GET.get('budget', 50))
    except ValueError:
        budget = 50
    menus = Menu.objects.filter(price__lte=budget).order_by('-created_at')[:12]
    return render(request, 'accounts/home.html', {'budget': budget, 'menus': menus})


# ---------- AUTH ----------
def register_view(request):
    if request.method == "POST":
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            form.save()
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
            return redirect('home')
        messages.error(request, "ชื่อผู้ใช้หรือรหัสผ่านไม่ถูกต้อง")
    else:
        form = LoginForm(request)
    return render(request, 'accounts/login.html', {'form': form})


def logout_view(request):
    logout(request)
    return redirect('login')


# ---------- PROFILE ----------
@login_required
def profile_view(request):
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
    return render(request, 'accounts/profile.html', {'uform': uform, 'pform': pform, 'profile': profile})


# ---------- วางแผนมื้ออาหาร ----------
@login_required
def plan_start(request):
    """
    หน้าเริ่มวางแผน (เลือกจำนวนวัน, วันที่เริ่ม, งบประมาณ)
    POST -> redirect ไปหน้าข้อจำกัด (plan_diet)
    """
    if request.method == 'POST':
        days = request.POST.get('days', '1')
        budget = request.POST.get('budget', '50')
        start_date = request.POST.get('start_date', '')
        # ส่งค่าไปหน้าข้อจำกัดด้วย query string
        return redirect(f"/accounts/plan/diet/?days={days}&budget={budget}&start_date={start_date}")
    return render(request, 'accounts/plan_start.html')


@login_required
def plan_diet(request):
    """
    หน้าเลือกข้อจำกัดอาหาร: แพ้/ไม่ชอบ/ศาสนา
    POST -> เก็บแผนลง session แล้วพาไปหน้า 'plan:summary'
    """
    # รับค่าที่ส่งมาจาก plan_start (ผ่าน query string)
    days = request.GET.get('days', '1')
    budget = request.GET.get('budget', '50')
    start_date = request.GET.get('start_date', '')

    # ตัวเลือกมาตรฐาน
    allergy_choices  = ["กุ้ง", "นม", "แป้งสาลี", "ไข่", "ถั่ว", "ทะเล (รวม)"]
    dislike_choices  = ["หมู", "ไก่", "เห็ด", "หัวหอม", "เครื่องใน", "ผักชี", "กระเทียม", "เนื้อวัว"]
    religion_choices = ["ฮาลาล", "มังสวิรัติ", "อาหารเจ", "หลีกเลี่ยงแอลกอฮอล์"]

    if request.method == 'POST':
        allergies = request.POST.getlist('allergies')
        dislikes  = request.POST.getlist('dislikes')
        religions = request.POST.getlist('religions')

        # เก็บ session สำหรับใช้คัดกรองเมนู/สรุปแผน/ทำตารางงบ
        request.session['plan'] = {
            'days': int(request.POST.get('days', '1') or 1),
            'budget': int(request.POST.get('budget', '50') or 50),
            'start_date': request.POST.get('start_date', ''),
            'allergies': allergies,
            'dislikes': dislikes,
            'religions': religions,
            'extra': {
                'allergy': request.POST.get('extra_allergy', '').strip(),
                'dislike': request.POST.get('extra_dislike', '').strip(),
                'religion': request.POST.get('extra_religion', '').strip(),
            }
        }
        # >>> เปลี่ยนปลายทาง ให้ไปหน้าแผนสรุป <<<
        return redirect('plan:summary')

    return render(request, 'accounts/plan_diet.html', {
        'days': days,
        'budget': budget,
        'start_date': start_date,
        'allergy_choices': allergy_choices,
        'dislike_choices': dislike_choices,
        'religion_choices': religion_choices,
    })
