from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.db.models import Count, Q
from django.http import Http404

from .models import Topic, Review, Comment, Like
from .forms import TopicForm, ReviewForm, CommentForm


# ================== Helper ==================

def staff_required(view_func):
    """ให้เฉพาะ user ที่เป็น staff เข้า view นี้ได้"""
    return user_passes_test(lambda u: u.is_staff)(view_func)


# ================== TOPIC LIST (หน้าแรก Community) ==================

@login_required
def topic_list(request):
    """
    หน้าแรก Community

    ตอนนี้ตั้งค่าให้ user ทุกคนเห็นหัวข้อของทุกคน
    (ถ้าไม่อยากโชว์หัวข้อที่ปิดไปจริง ๆ ให้ตั้ง is_active=False แล้วกรองด้วย is_active=True)
    """
    topics = (
        Topic.objects.all()              # เห็นทุกหัวข้อ
        .annotate(reviews_count=Count("reviews"))
        .order_by("-created_at")
    )

    return render(request, "community/topic_list.html", {
        "topics": topics,
    })


# ================== ADD / EDIT / DELETE TOPIC ==================

@login_required
def topic_add(request):
    """
    user สร้างหัวข้อได้
    ตอนนี้จะถือว่า “อนุมัติทันที” ให้ทุกคนเห็นเลย (status='approved')
    ถ้าอยากกลับไปมีระบบอนุมัติ สามารถเปลี่ยน logic ตรงนี้ทีหลังได้
    """
    if request.method == "POST":
        form = TopicForm(request.POST, request.FILES)
        if form.is_valid():
            topic = form.save(commit=False)
            topic.created_by = request.user
            topic.status = "approved"    # อนุมัติทันที
            topic.is_active = True
            topic.save()
            messages.success(request, "สร้างหัวข้อเรียบร้อย")
            return redirect("community:topic_detail", pk=topic.pk)
    else:
        form = TopicForm()

    return render(request, "community/topic_form.html", {
        "form": form,
    })


@login_required
def topic_edit(request, pk):
    """
    แก้ไขหัวข้อ
    - ทำได้เฉพาะคนสร้างหัวข้อเอง หรือ staff
    """
    topic = get_object_or_404(Topic, pk=pk)

    if not (request.user == topic.created_by or request.user.is_staff):
        raise Http404()

    if request.method == "POST":
        form = TopicForm(request.POST, request.FILES, instance=topic)
        if form.is_valid():
            t = form.save(commit=False)
            # แก้ไขแล้วให้ยังคง approved อยู่
            if t.status != "approved":
                t.status = "approved"
            t.save()
            messages.success(request, "แก้ไขหัวข้อเรียบร้อย")
            return redirect("community:topic_detail", pk=topic.pk)
    else:
        form = TopicForm(instance=topic)

    return render(request, "community/topic_form.html", {
        "form": form,
        "topic": topic,
    })


@login_required
def topic_delete(request, pk):
    """
    ลบหัวข้อ
    - ทำได้เฉพาะคนสร้างหัวข้อเอง หรือ staff
    """
    topic = get_object_or_404(Topic, pk=pk)

    if not (request.user == topic.created_by or request.user.is_staff):
        raise Http404()

    if request.method == "POST":
        topic.delete()
        messages.success(request, "ลบหัวข้อเรียบร้อย")
        return redirect("community:topic_list")

    return render(request, "community/topic_delete_confirm.html", {
        "topic": topic,
    })


# ================== TOPIC DETAIL + REVIEW LIST ==================

@login_required
def topic_detail(request, pk):
    """
    หน้ารายละเอียดหัวข้อ + รายการรีวิว

    ตอนนี้เปิดให้ user ทุกคนเข้าอ่านหัวข้อได้
    (ยกเว้นถ้าอยาก soft delete ให้ตั้ง is_active=False แล้วบัง)
    """
    topic = get_object_or_404(Topic, pk=pk)

    # ถ้าอยากบังหัวข้อที่ปิดไปจริง ๆ
    if not topic.is_active:
        raise Http404()

    keyword = request.GET.get("q", "").strip()

    reviews = Review.objects.filter(topic=topic).annotate(
        likes_count=Count("likes"),
        comments_count=Count("comments"),
    )

    # ถ้ายังอยากให้เห็นทุกรีวิวของทุกคนเลย ก็ไม่ต้องกรองตาม status
    # ถ้าอยากกรองให้เห็นเฉพาะ approved ให้เปิดบรรทัดนี้แทน
    # if not request.user.is_staff:
    #     reviews = reviews.filter(Q(status="approved") | Q(author=request.user))

    if keyword:
        reviews = reviews.filter(
            Q(title__icontains=keyword) |
            Q(body__icontains=keyword)
        )

    return render(request, "community/topic_detail.html", {
        "topic": topic,
        "reviews": reviews,
        "keyword": keyword,
    })


# ================== ADD / EDIT / DELETE REVIEW ==================

@login_required
def review_add(request, pk):
    """
    เพิ่มรีวิวให้หัวข้อ
    ตอนนี้อนุมัติทันที (status='approved') ให้ทุกคนเห็น
    """
    topic = get_object_or_404(Topic, pk=pk)

    if request.method == "POST":
        form = ReviewForm(request.POST, request.FILES)
        if form.is_valid():
            review = form.save(commit=False)
            review.topic = topic
            review.author = request.user
            review.status = "approved"
            review.save()
            messages.success(request, "เพิ่มรีวิวเรียบร้อยแล้ว")
            return redirect("community:topic_detail", pk=topic.pk)
    else:
        form = ReviewForm()

    return render(request, "community/review_form.html", {
        "form": form,
        "topic": topic,
    })


@login_required
def review_edit(request, pk):
    """
    แก้ไขรีวิว
    - เจ้าของรีวิวหรือ staff เท่านั้น
    """
    review = get_object_or_404(Review, pk=pk)

    if review.author != request.user and not request.user.is_staff:
        raise Http404()

    if request.method == "POST":
        form = ReviewForm(request.POST, request.FILES, instance=review)
        if form.is_valid():
            r = form.save(commit=False)
            r.status = "approved"
            r.save()
            messages.success(request, "แก้ไขรีวิวเรียบร้อย")
            return redirect("community:topic_detail", pk=review.topic_id)
    else:
        form = ReviewForm(instance=review)

    return render(request, "community/review_form.html", {
        "form": form,
        "topic": review.topic,
        "review": review,
    })


@login_required
def review_delete(request, pk):
    """
    ลบรีวิว
    - เจ้าของรีวิวหรือ staff เท่านั้น
    """
    review = get_object_or_404(Review, pk=pk)

    if review.author != request.user and not request.user.is_staff:
        raise Http404()

    if request.method == "POST":
        tid = review.topic_id
        review.delete()
        messages.success(request, "ลบรีวิวเรียบร้อย")
        return redirect("community:topic_detail", pk=tid)

    return render(request, "community/review_delete.html", {
        "review": review,
    })


# ================== COMMENT ==================

@login_required
def comment_add(request, pk):
    review = get_object_or_404(Review, pk=pk)

    if request.method == "POST":
        form = CommentForm(request.POST)
        if form.is_valid():
            c = form.save(commit=False)
            c.review = review
            c.user = request.user
            c.save()
    return redirect("community:topic_detail", pk=review.topic_id)


@login_required
def comment_delete(request, pk):
    c = get_object_or_404(Comment, pk=pk)

    if c.user != request.user and not request.user.is_staff:
        raise Http404()

    tid = c.review.topic_id
    c.delete()
    return redirect("community:topic_detail", pk=tid)


# ================== LIKE ==================

@login_required
def review_like_toggle(request, pk):
    """
    toggle ปุ่มถูกใจรีวิว
    - ถ้าเคยกดแล้ว -> ลบ like
    - ถ้ายังกดไม่เคย -> สร้าง like ใหม่
    """
    review = get_object_or_404(Review, pk=pk)

    like, created = Like.objects.get_or_create(
        review=review,
        user=request.user,
    )

    if not created:
        like.delete()

    return redirect("community:topic_detail", pk=review.topic_id)


# ================== MODERATION (เฉพาะ STAFF – ถ้าอยากใช้ทีหลังยังเก็บไว้ได้) ==================

@staff_required
def topic_moderation_list(request):
    topics = Topic.objects.filter(status="pending").order_by("created_at")
    return render(request, "community/topic_moderation_list.html", {
        "topics": topics,
    })


@staff_required
def topic_approve(request, pk):
    topic = get_object_or_404(Topic, pk=pk)
    topic.status = "approved"
    topic.is_active = True
    topic.save()
    return redirect("community:topic_moderation_list")


@staff_required
def topic_reject(request, pk):
    topic = get_object_or_404(Topic, pk=pk)
    topic.status = "rejected"
    topic.save()
    return redirect("community:topic_moderation_list")


@staff_required
def review_moderation_list(request):
    reviews = Review.objects.filter(status="pending").order_by("created_at")
    return render(request, "community/review_moderation_list.html", {
        "reviews": reviews,
    })


@staff_required
def review_approve(request, pk):
    review = get_object_or_404(Review, pk=pk)
    review.status = "approved"
    review.save()
    return redirect("community:review_moderation_list")


@staff_required
def review_reject(request, pk):
    review = get_object_or_404(Review, pk=pk)
    review.status = "rejected"
    review.save()
    return redirect("community:review_moderation_list")
