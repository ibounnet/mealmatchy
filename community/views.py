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
    - staff เห็นทุกหัวข้อที่ is_active=True
    - user ทั่วไป เห็นเฉพาะหัวข้อที่อนุมัติแล้ว (status='approved')
      หรือหัวข้อที่ตัวเองเป็นคนสร้าง
    """
    base_qs = Topic.objects.filter(is_active=True)

    if request.user.is_staff:
        topics = base_qs
    else:
        topics = base_qs.filter(
            Q(status="approved") | Q(created_by=request.user)
        )

    topics = topics.annotate(reviews_count=Count("reviews"))

    return render(request, "community/topic_list.html", {
        "topics": topics,
    })


# ================== ADD / EDIT / DELETE TOPIC ==================

@login_required
def topic_add(request):
    """
    user สร้างหัวข้อได้
    - ถ้าเป็น staff สร้างแล้วให้อนุมัติเลย (status='approved')
    - ถ้าเป็น user ทั่วไป ให้ตั้งสถานะเป็น pending รอ staff อนุมัติ
    """
    if request.method == "POST":
        form = TopicForm(request.POST, request.FILES)
        if form.is_valid():
            topic = form.save(commit=False)
            topic.created_by = request.user
            if request.user.is_staff:
                topic.status = "approved"
            else:
                topic.status = "pending"
            topic.is_active = True
            topic.save()
            messages.success(
                request,
                "ส่งหัวข้อเรียบร้อย กำลังรอการอนุมัติจากผู้ดูแล"
                if not request.user.is_staff
                else "สร้างหัวข้อเรียบร้อย"
            )
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
    - ถ้าไม่ใช่ staff เมื่อแก้ไขแล้วให้กลับไปเป็น pending รออนุมัติใหม่
    """
    topic = get_object_or_404(Topic, pk=pk)

    if not (request.user == topic.created_by or request.user.is_staff):
        raise Http404()

    if request.method == "POST":
        form = TopicForm(request.POST, request.FILES, instance=topic)
        if form.is_valid():
            t = form.save(commit=False)
            if request.user.is_staff:
                # staff แก้แล้วให้คงสถานะเดิม ถ้าอยากให้อนุมัติทันที
                if t.status == "pending":
                    t.status = "approved"
            else:
                # user แก้ไข -> กลับไป pending
                t.status = "pending"
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
    - ถ้าเป็นหัวข้อที่ยังไม่ได้ approved:
        - owner ของหัวข้อและ staff ดูได้
        - คนอื่นห้ามดู
    - รีวิว:
        - staff เห็นทุก status
        - user เห็นเฉพาะ review ที่ approved หรือที่ตัวเองเขียน
    """
    topic = get_object_or_404(Topic, pk=pk)

    if (
        not request.user.is_staff
        and topic.status != "approved"
        and topic.created_by != request.user
    ):
        raise Http404()

    keyword = request.GET.get("q", "").strip()

    reviews = Review.objects.filter(topic=topic).annotate(
        likes_count=Count("likes"),
        comments_count=Count("comments"),
    )

    if not request.user.is_staff:
        reviews = reviews.filter(
            Q(status="approved") | Q(author=request.user)
        )

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
    - หัวข้อที่ยังไม่ approved: ให้รีวิวได้เฉพาะ owner + staff
    - ทุกรีวิวของ user ทั่วไปจะเริ่มด้วย status='pending'
    """
    topic = get_object_or_404(Topic, pk=pk)

    if (
        not request.user.is_staff
        and topic.status != "approved"
        and topic.created_by != request.user
    ):
        raise Http404()

    if request.method == "POST":
        form = ReviewForm(request.POST, request.FILES)
        if form.is_valid():
            review = form.save(commit=False)
            review.topic = topic
            review.author = request.user
            review.status = "pending"
            review.save()
            messages.success(
                request,
                "ส่งรีวิวเรียบร้อย กำลังรอการอนุมัติจากผู้ดูแล"
            )
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
    - ถ้าเจ้าของแก้ไข ให้กลับเป็น pending
    """
    review = get_object_or_404(Review, pk=pk)

    if review.author != request.user and not request.user.is_staff:
        raise Http404()

    if request.method == "POST":
        form = ReviewForm(request.POST, request.FILES, instance=review)
        if form.is_valid():
            r = form.save(commit=False)
            if not request.user.is_staff:
                r.status = "pending"
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


# ================== MODERATION (เฉพาะ STAFF) ==================

@staff_required
def topic_moderation_list(request):
    """
    หน้าให้ staff ตรวจหัวข้อที่สถานะ pending
    """
    topics = Topic.objects.filter(status="pending").order_by("created_at")
    return render(request, "community/topic_moderation_list.html", {
        "topics": topics,
    })


@staff_required
def topic_approve(request, pk):
    """
    staff กดอนุมัติหัวข้อ
    """
    topic = get_object_or_404(Topic, pk=pk)
    topic.status = "approved"
    topic.is_active = True
    topic.save()
    return redirect("community:topic_moderation_list")


@staff_required
def topic_reject(request, pk):
    """
    staff ปฏิเสธหัวข้อ
    """
    topic = get_object_or_404(Topic, pk=pk)
    topic.status = "rejected"
    topic.save()
    return redirect("community:topic_moderation_list")


@staff_required
def review_moderation_list(request):
    """
    หน้าให้ staff ตรวจรีวิวที่สถานะ pending
    """
    reviews = Review.objects.filter(status="pending").order_by("created_at")
    return render(request, "community/review_moderation_list.html", {
        "reviews": reviews,
    })


@staff_required
def review_approve(request, pk):
    """
    staff อนุมัติรีวิว
    """
    review = get_object_or_404(Review, pk=pk)
    review.status = "approved"
    review.save()
    return redirect("community:review_moderation_list")


@staff_required
def review_reject(request, pk):
    """
    staff ปฏิเสธรีวิว
    """
    review = get_object_or_404(Review, pk=pk)
    review.status = "rejected"
    review.save()
    return redirect("community:review_moderation_list")
