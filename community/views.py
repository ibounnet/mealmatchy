# community/views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.db.models import Count, Q
from django.http import Http404
from django.views.decorators.http import require_POST

from .models import Topic, Review, Comment, Like
from .forms import TopicForm, ReviewForm, CommentForm


# ================== Helper ==================
def staff_required(view_func):
    """ให้เฉพาะ user ที่เป็น staff เข้า view นี้ได้"""
    return user_passes_test(lambda u: u.is_staff)(view_func)


# ================== TOPIC LIST (หน้าแรก Community) ==================
def topic_list(request):
    """
    หน้าแรก Community
    - ไม่ล็อกอิน: เห็นเฉพาะ approved
    - ล็อกอิน:
        staff -> เห็นทั้งหมด (is_active=True)
        user -> เห็น approved + ที่ตัวเองสร้าง
    """
    base_qs = Topic.objects.filter(is_active=True)

    my_topics = Topic.objects.none()
    if request.user.is_authenticated:
        my_topics = (
            base_qs.filter(created_by=request.user)
            .annotate(reviews_count=Count("reviews"))
            .order_by("-created_at")
        )

        if request.user.is_staff:
            topics = base_qs
        else:
            topics = base_qs.filter(Q(status="approved") | Q(created_by=request.user))
    else:
        topics = base_qs.filter(status="approved")

    topics = topics.annotate(reviews_count=Count("reviews")).order_by("-created_at")

    return render(request, "community/topic_list.html", {
        "topics": topics,
        "my_topics": my_topics,
    })


# ================== ADD / EDIT / DELETE TOPIC ==================
@login_required
def topic_add(request):
    if request.method == "POST":
        form = TopicForm(request.POST, request.FILES)
        if form.is_valid():
            topic = form.save(commit=False)
            topic.created_by = request.user
            topic.status = "approved"
            topic.is_active = True
            topic.save()
            messages.success(request, "สร้างหัวข้อเรียบร้อย")
            return redirect("community:topic_detail", pk=topic.pk)
        messages.error(request, "สร้างหัวข้อไม่สำเร็จ กรุณาตรวจสอบข้อมูล")
    else:
        form = TopicForm()

    return render(request, "community/topic_form.html", {"form": form})


@login_required
def topic_edit(request, pk):
    topic = get_object_or_404(Topic, pk=pk)
    if not (request.user == topic.created_by or request.user.is_staff):
        raise Http404()

    if request.method == "POST":
        form = TopicForm(request.POST, request.FILES, instance=topic)
        if form.is_valid():
            t = form.save(commit=False)
            t.status = "approved"
            t.save()
            messages.success(request, "แก้ไขหัวข้อเรียบร้อย")
            return redirect("community:topic_detail", pk=topic.pk)
        messages.error(request, "แก้ไขไม่สำเร็จ กรุณาตรวจสอบข้อมูล")
    else:
        form = TopicForm(instance=topic)

    return render(request, "community/topic_form.html", {"form": form, "topic": topic})


@login_required
def topic_delete(request, pk):
    topic = get_object_or_404(Topic, pk=pk)
    if not (request.user == topic.created_by or request.user.is_staff):
        raise Http404()

    if request.method == "POST":
        topic.delete()
        messages.success(request, "ลบหัวข้อเรียบร้อย")
        return redirect("community:topic_list")

    return render(request, "community/topic_delete_confirm.html", {"topic": topic})


# ================== TOPIC DETAIL + REVIEW LIST ==================
def topic_detail(request, pk):
    """
    หน้ารายละเอียดหัวข้อ + รายการรีวิว
    - ให้ดูได้แม้ไม่ล็อกอิน (ถ้าอยากบังคับล็อกอินค่อยใส่ @login_required กลับ)
    - แต่การคอมเม้น/ไลก์ ยังบังคับล็อกอินใน view ที่เกี่ยวข้องอยู่แล้ว
    """
    topic = get_object_or_404(Topic, pk=pk)

    if (not request.user.is_staff) and (not topic.is_active) and (topic.created_by != request.user):
        raise Http404()

    keyword = (request.GET.get("q") or "").strip()

    reviews = (
        Review.objects
        .filter(topic=topic)
        .select_related("author")
        .prefetch_related("comments__user", "likes")
        .annotate(
            likes_count=Count("likes", distinct=True),
            comments_count=Count("comments", distinct=True),
        )
    )

    if not request.user.is_staff:
        reviews = reviews.exclude(status="rejected")

    if keyword:
        reviews = reviews.filter(Q(title__icontains=keyword) | Q(body__icontains=keyword))

    reviews = reviews.order_by("-created_at")

    return render(request, "community/topic_detail.html", {
        "topic": topic,
        "reviews": reviews,
        "keyword": keyword,
        "comment_form": CommentForm(),  # ส่งฟอร์มให้ template ใช้
    })


# ================== ADD / EDIT / DELETE REVIEW ==================
@login_required
def review_add(request, pk):
    topic = get_object_or_404(Topic, pk=pk)

    if request.method == "POST":
        form = ReviewForm(request.POST, request.FILES)
        if form.is_valid():
            review = form.save(commit=False)
            review.topic = topic
            review.author = request.user
            review.status = "approved"
            review.save()
            messages.success(request, "เพิ่มรีวิวเรียบร้อย")
            return redirect("community:topic_detail", pk=topic.pk)
        messages.error(request, "เพิ่มรีวิวไม่สำเร็จ กรุณาตรวจสอบข้อมูล")
    else:
        form = ReviewForm()

    return render(request, "community/review_form.html", {"form": form, "topic": topic})


@login_required
def review_edit(request, pk):
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
        messages.error(request, "แก้ไขไม่สำเร็จ กรุณาตรวจสอบข้อมูล")
    else:
        form = ReviewForm(instance=review)

    return render(request, "community/review_form.html", {
        "form": form,
        "topic": review.topic,
        "review": review,
    })


@login_required
def review_delete(request, pk):
    review = get_object_or_404(Review, pk=pk)

    if review.author != request.user and not request.user.is_staff:
        raise Http404()

    if request.method == "POST":
        tid = review.topic_id
        review.delete()
        messages.success(request, "ลบรีวิวเรียบร้อย")
        return redirect("community:topic_detail", pk=tid)

    return render(request, "community/review_delete.html", {"review": review})


# ================== COMMENT ==================
@login_required
@require_POST
def comment_add(request, pk):
    review = get_object_or_404(Review, pk=pk)

    form = CommentForm(request.POST)
    if form.is_valid():
        c = form.save(commit=False)
        c.review = review
        c.user = request.user
        c.save()
        messages.success(request, "ส่งความคิดเห็นเรียบร้อย")
    else:
        messages.error(request, "ส่งไม่สำเร็จ: กรุณาพิมพ์ความคิดเห็นก่อน")

    return redirect("community:topic_detail", pk=review.topic_id)


@login_required
@require_POST
def comment_delete(request, pk):
    c = get_object_or_404(Comment, pk=pk)

    if c.user != request.user and not request.user.is_staff:
        raise Http404()

    tid = c.review.topic_id
    c.delete()
    messages.success(request, "ลบความคิดเห็นเรียบร้อย")
    return redirect("community:topic_detail", pk=tid)


# ================== LIKE ==================
@login_required
def review_like_toggle(request, pk):
    review = get_object_or_404(Review, pk=pk)

    like, created = Like.objects.get_or_create(review=review, user=request.user)
    if not created:
        like.delete()

    return redirect("community:topic_detail", pk=review.topic_id)


# ================== MODERATION (เฉพาะ STAFF) ==================
@staff_required
def topic_moderation_list(request):
    topics = Topic.objects.filter(status="pending").order_by("created_at")
    return render(request, "community/topic_moderation_list.html", {"topics": topics})


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
    return render(request, "community/review_moderation_list.html", {"reviews": reviews})


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
