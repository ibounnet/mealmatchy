from django.db import models
from django.contrib.auth.models import User
from uuid import uuid4
import os
from decimal import Decimal, ROUND_HALF_UP

from menus.models import Ingredient


def recipe_image_path(instance, filename):
    ext = filename.split(".")[-1]
    return os.path.join("recipe_images", f"{uuid4()}.{ext}")


# ----------------------------
# User setting: Hybrid cost
# ----------------------------
class UserCookingCostSetting(models.Model):
    MODE_CHOICES = [
        ("basic", "Basic (เฉลี่ย)"),
        ("advanced", "Advanced (คิดตามเตา/เวลา)"),
    ]
    STOVE_CHOICES = [
        ("electric", "เตาไฟฟ้า"),
        ("induction", "เตาแม่เหล็กไฟฟ้า (Induction)"),
        ("gas", "เตาแก๊ส"),
    ]

    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name="cooking_cost_setting"
    )

    mode = models.CharField(max_length=20, choices=MODE_CHOICES, default="basic")

    # Basic (บาท/เสิร์ฟ)
    seasoning_cost_per_serving = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal("5.00")
    )
    overhead_cost_per_serving = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal("3.00")
    )

    # Advanced defaults
    default_stove_type = models.CharField(
        max_length=20, choices=STOVE_CHOICES, default="electric"
    )
    default_cook_minutes = models.PositiveIntegerField(default=10)

    # ค่าไฟ
    electricity_rate_per_kwh = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal("4.00")
    )
    electric_power_watt = models.PositiveIntegerField(default=1200)
    induction_power_watt = models.PositiveIntegerField(default=1500)

    # ค่าแก๊ส (บาท/ชั่วโมง)
    gas_cost_per_hour = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal("10.00")
    )

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "User cooking cost setting"
        verbose_name_plural = "User cooking cost settings"

    def __str__(self):
        return f"CookingCostSetting({self.user.username})"

    # -------- helpers (safe) --------
    @staticmethod
    def get_or_create_for_user(user: User) -> "UserCookingCostSetting":
        obj, _ = UserCookingCostSetting.objects.get_or_create(user=user)
        return obj

    def basic_extra_cost_total(self, servings: int) -> Decimal:
        """
        Basic: (seasoning + overhead) * servings
        """
        s = max(int(servings or 1), 1)
        total = (self.seasoning_cost_per_serving or Decimal("0")) + (self.overhead_cost_per_serving or Decimal("0"))
        return (total * Decimal(s)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    def advanced_energy_cost(self, stove_type: str, cook_minutes: int) -> Decimal:
        """
        Advanced: คิดค่าไฟ/แก๊สจากเตา + นาที
        - electric/induction: kWh = (W/1000) * (minutes/60) ; cost = kWh * rate
        - gas: cost = (minutes/60) * gas_cost_per_hour
        """
        m = max(int(cook_minutes or 0), 0)
        if m <= 0:
            return Decimal("0.00")

        stove = (stove_type or "").strip().lower()

        if stove in ("electric", "induction"):
            rate = Decimal(str(self.electricity_rate_per_kwh or "0"))
            watt = self.electric_power_watt if stove == "electric" else self.induction_power_watt
            watt = max(int(watt or 0), 0)

            if watt <= 0 or rate <= 0:
                return Decimal("0.00")

            kwh = (Decimal(watt) / Decimal("1000")) * (Decimal(m) / Decimal("60"))
            cost = kwh * rate
            return cost.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

        if stove == "gas":
            gas_rate = Decimal(str(self.gas_cost_per_hour or "0"))
            if gas_rate <= 0:
                return Decimal("0.00")
            cost = (Decimal(m) / Decimal("60")) * gas_rate
            return cost.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

        # unknown stove -> 0
        return Decimal("0.00")


# ----------------------------
# Recipe + RecipeIngredient
# ----------------------------
class Recipe(models.Model):
    STOVE_CHOICES = UserCookingCostSetting.STOVE_CHOICES

    title = models.CharField(max_length=200)
    restaurant_name = models.CharField(max_length=200, blank=True)
    description = models.TextField(blank=True)

    # ช่องเดิมยังเก็บไว้ได้ แต่ "ไม่บังคับ"
    ingredients = models.TextField(blank=True)
    steps = models.TextField(blank=True)

    servings = models.PositiveIntegerField(default=1)
    prep_minutes = models.PositiveIntegerField(default=0)
    cook_minutes = models.PositiveIntegerField(default=0)

    # ✅ optional: สูตรสามารถ override เตาได้ (ถ้าไม่กรอก -> ใช้ setting ผู้ใช้)
    stove_type = models.CharField(
        max_length=20,
        choices=STOVE_CHOICES,
        null=True,
        blank=True,
        default=None,
        help_text="ถ้าไม่เลือก ระบบจะใช้ค่า default จากการตั้งค่าผู้ใช้",
    )

    image = models.ImageField(upload_to=recipe_image_path, blank=True, null=True)

    created_by = models.ForeignKey(
        User, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="recipes"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.title

    @property
    def total_minutes(self):
        return (self.prep_minutes or 0) + (self.cook_minutes or 0)

    @property
    def ingredients_cost(self) -> Decimal:
        """
        ต้นทุนวัตถุดิบรวม (จาก snapshot)
        """
        total = Decimal("0")
        for ri in self.recipe_ingredients.all():
            total += (ri.cost_snapshot or Decimal("0"))
        return total.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    @property
    def total_cost(self) -> Decimal:
        """
        ยังคงเดิม: total_cost = ต้นทุนวัตถุดิบรวม
        (ส่วนต้นทุนแฝง/เครื่องปรุงจะไปคำนวณใน view ตาม setting user เพื่อ UX hybrid)
        """
        return self.ingredients_cost


class RecipeIngredient(models.Model):
    """
    ตารางเชื่อมระหว่าง Recipe กับ Ingredient
    เก็บ grams + snapshot ราคา/ต้นทุน ณ วันที่บันทึก
    """
    recipe = models.ForeignKey(
        Recipe, on_delete=models.CASCADE, related_name="recipe_ingredients"
    )
    ingredient = models.ForeignKey(
        Ingredient, on_delete=models.PROTECT, related_name="used_in_recipes"
    )

    quantity_grams = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0"))
    price_per_gram_snapshot = models.DecimalField(max_digits=12, decimal_places=6, default=Decimal("0"))
    cost_snapshot = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0"))

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = (("recipe", "ingredient"),)
        ordering = ["id"]

    def __str__(self):
        return f"{self.recipe_id} - {self.ingredient_id} ({self.quantity_grams}g)"

    @staticmethod
    def get_price_per_gram_from_ingredient(ingredient: Ingredient) -> Decimal:
        """
        - ถ้า Ingredient มี price_per_gram ใช้เลย
        - ถ้าไม่มี ลองคำนวณจาก price/size_grams (ถ้ามี field)
        - ไม่ได้จริง ๆ คืน 0
        """
        try:
            ppg = getattr(ingredient, "price_per_gram", None)
            if ppg is not None:
                return Decimal(str(ppg))
        except Exception:
            pass

        try:
            price = getattr(ingredient, "price", None)
            size = getattr(ingredient, "size_grams", None)
            if price is not None and size is not None and Decimal(str(size)) > 0:
                return (Decimal(str(price)) / Decimal(str(size))).quantize(
                    Decimal("0.000001"), rounding=ROUND_HALF_UP
                )
        except Exception:
            pass

        return Decimal("0")

    def recalc_cost(self, save: bool = False):
        """
        cost = grams * price_per_gram_snapshot
        """
        q = self.quantity_grams or Decimal("0")
        p = self.price_per_gram_snapshot or Decimal("0")
        self.cost_snapshot = (q * p).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        if save:
            self.save(update_fields=["cost_snapshot"])
        return self.cost_snapshot
