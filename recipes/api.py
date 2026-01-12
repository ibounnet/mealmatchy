# recipes/api.py
import json
from decimal import Decimal, ROUND_HALF_UP

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponseBadRequest
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_GET, require_POST

from menus.models import Ingredient


def _dec(x, default="0"):
    try:
        return Decimal(str(x))
    except Exception:
        return Decimal(default)


@require_GET
@login_required
def ingredient_detail(request, pk):
    ing = get_object_or_404(Ingredient, pk=pk)

    ppg = Decimal("0")
    if hasattr(ing, "price_per_gram") and getattr(ing, "price_per_gram") is not None:
        ppg = _dec(getattr(ing, "price_per_gram"))
    else:
        # เผื่อโมเดล Ingredient มี price/size_grams
        price = getattr(ing, "price", None)
        size = getattr(ing, "size_grams", None)
        try:
            if price is not None and size is not None and _dec(size) > 0:
                ppg = (_dec(price) / _dec(size))
        except Exception:
            ppg = Decimal("0")

    ppg = ppg.quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)

    return JsonResponse({
        "id": ing.id,
        "name": ing.name,
        "price_per_gram": str(ppg),
    })


@require_POST
@login_required
def ingredient_create(request):
    try:
        payload = json.loads(request.body.decode("utf-8"))
    except Exception:
        return HttpResponseBadRequest("invalid json")

    name = (payload.get("name") or "").strip()
    if not name:
        return JsonResponse({"ok": False, "error": "name required"}, status=400)

    ppg = _dec(payload.get("price_per_gram", 0)).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)

    ing, created = Ingredient.objects.get_or_create(name=name)

    # ถ้ามี field price_per_gram ก็อัปเดตให้
    if hasattr(ing, "price_per_gram"):
        try:
            ing.price_per_gram = ppg
            ing.save(update_fields=["price_per_gram"])
        except Exception:
            pass

    # อ่านกลับ
    final_ppg = getattr(ing, "price_per_gram", None)
    final_ppg = _dec(final_ppg or "0").quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)

    return JsonResponse({
        "ok": True,
        "id": ing.id,
        "name": ing.name,
        "price_per_gram": str(final_ppg),
        "created": created,
    })
