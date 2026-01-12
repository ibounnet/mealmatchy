import csv
import re
from decimal import Decimal
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from menus.models import Ingredient


def to_decimal(v, default="0"):
    try:
        return Decimal(str(v))
    except Exception:
        return Decimal(default)


def parse_price(text) -> Decimal:
    if not text:
        return Decimal("0")
    s = str(text).replace(",", "").strip()
    m = re.search(r"(\d+(\.\d+)?)", s)
    return to_decimal(m.group(1)) if m else Decimal("0")


def parse_grams_from_th_name(name: str) -> Decimal:
    """
    ดึงน้ำหนักจากชื่อสินค้าไทย -> กรัม
    รองรับ:
      - "150 กรัม", "150 ก.", "250 ก"
      - "1 กก.", "1กก", "1000 กรัม"
      - "กก. ละ" / "กก.ละ" => ถือว่า 1000 กรัม (ราคาต่อกิโลกรัม)
      - "150 กรัม แพ็ค 3" => 150*3
    """
    if not name:
        return Decimal("0")

    s = str(name).lower()
    s = s.replace(" ", "")
    s = s.replace(",", "")

    # ราคาต่อกิโลกรัม
    if "กก.ละ" in s or "กกละ" in s or "กก.ล่ะ" in s:
        return Decimal("1000")

    # แพ็ค: 150กรัมแพ็ค3
    m_pack = re.search(r"(\d+(\.\d+)?)(กรัม|ก\.|ก)(?:แพ็ค|แพค)(\d+)", s)
    if m_pack:
        per = to_decimal(m_pack.group(1))
        pack_n = to_decimal(m_pack.group(4))
        return (per * pack_n).quantize(Decimal("0.01"))

    # กรัม: 150กรัม / 150ก. / 150ก
    m_g = re.search(r"(\d+(\.\d+)?)(กรัม|ก\.|ก)", s)
    if m_g:
        return to_decimal(m_g.group(1)).quantize(Decimal("0.01"))

    # กิโล: 1กก / 1.5กก
    m_kg = re.search(r"(\d+(\.\d+)?)(กก\.|กก)", s)
    if m_kg:
        kg = to_decimal(m_kg.group(1))
        return (kg * Decimal("1000")).quantize(Decimal("0.01"))

    return Decimal("0")


def normalize_name(name: str) -> str:
    if not name:
        return ""
    s = name.strip()
    # ตัดหน่วยท้าย ๆ ให้ dropdown อ่านง่าย
    s = re.sub(r"\s*\d+(\.\d+)?\s*(กรัม|ก\.|ก)\s*(แพ็ค|แพค)\s*\d+\s*$", "", s, flags=re.IGNORECASE)
    s = re.sub(r"\s*\d+(\.\d+)?\s*(กรัม|ก\.|ก)\s*$", "", s, flags=re.IGNORECASE)
    s = re.sub(r"\s*\d+(\.\d+)?\s*(กก\.|กก)\s*$", "", s, flags=re.IGNORECASE)
    s = re.sub(r"\s*(กก\.?\s*ละ|กก\.?ละ)\s*$", "", s, flags=re.IGNORECASE)
    s = re.sub(r"\s{2,}", " ", s).strip()
    return s


class Command(BaseCommand):
    help = "Import Lotus CSV (ชื่อสินค้า,ราคา) -> menus.Ingredient"

    def add_arguments(self, parser):
        parser.add_argument("filepaths", nargs="+", type=str)

    def handle(self, *args, **options):
        filepaths = [Path(p) for p in options["filepaths"]]

        created_count = 0
        updated_count = 0
        skipped_count = 0

        for fp in filepaths:
            if not fp.exists():
                raise CommandError(f"File not found: {fp}")
            if fp.suffix.lower() != ".csv":
                raise CommandError(f"Only .csv supported: {fp}")

            with fp.open("r", encoding="utf-8-sig", newline="") as f:
                reader = csv.DictReader(f)
                if not reader.fieldnames:
                    raise CommandError(f"CSV has no header: {fp}")

                if "ชื่อสินค้า" not in reader.fieldnames or "ราคา" not in reader.fieldnames:
                    raise CommandError(f"CSV ต้องมีหัวตาราง: ชื่อสินค้า, ราคา | header ที่เจอ: {reader.fieldnames}")

                for row in reader:
                    raw_name = (row.get("ชื่อสินค้า") or "").strip()
                    if not raw_name:
                        skipped_count += 1
                        continue

                    price = parse_price(row.get("ราคา"))
                    grams = parse_grams_from_th_name(raw_name)

                    if grams <= 0:
                        skipped_count += 1
                        continue

                    ppg = (price / grams).quantize(Decimal("0.0001"))
                    clean_name = normalize_name(raw_name)

                    obj, created = Ingredient.objects.update_or_create(
                        name=clean_name,
                        defaults={
                            "name": clean_name,
                            "source": "lotus",
                            "price": price,
                            "size_grams": grams,
                            "price_per_gram": ppg,
                        },
                    )

                    if created:
                        created_count += 1
                    else:
                        updated_count += 1

        self.stdout.write(self.style.SUCCESS(
            f"Import done: created={created_count}, updated={updated_count}, skipped={skipped_count}"
        ))
