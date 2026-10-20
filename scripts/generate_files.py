#!/usr/bin/env python3
"""Generate deterministic retail transaction CSV fixtures using only the standard library."""

import csv
import random
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path

SEED = 42
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data" / "generated"
SAMPLE_PATH = BASE_DIR / "data" / "sample.csv"

HEADER = [
    "transaction_id", "store_code", "sold_at", "sku", "product_name",
    "quantity", "unit_price", "discount", "payment_mode",
    "original_transaction_id",
]
STORES = [f"ST{i:02d}" for i in range(1, 7)]
PRODUCTS = [
    ("SKU-114", "Basmati Rice 5kg", "540.00"),
    ("SKU-201", "Toor Dal 1kg", "165.00"),
    ("SKU-305", "Amul Butter 500g", "285.00"),
    ("SKU-422", "Sunflower Oil 1L", "152.50"),
    ("SKU-518", "Tata Tea Gold 500g", "245.00"),
    ("SKU-106", "Atta 5kg", "265.00"),
    ("SKU-107", "Sugar 1kg", "48.00"),
    ("SKU-108", "Iodized Salt 1kg", "25.00"),
    ("SKU-109", "Poha 1kg", "68.00"),
    ("SKU-110", "Rava 1kg", "55.00"),
    ("SKU-111", "Moong Dal 1kg", "145.00"),
    ("SKU-112", "Chana Dal 1kg", "92.00"),
    ("SKU-113", "Urad Dal 1kg", "138.00"),
    ("SKU-115", "Brown Rice 1kg", "95.00"),
    ("SKU-116", "Wheat Flour 1kg", "54.00"),
    ("SKU-202", "Masoor Dal 1kg", "112.00"),
    ("SKU-203", "Rajma 500g", "78.00"),
    ("SKU-204", "Kabuli Chana 1kg", "118.00"),
    ("SKU-205", "Besan 1kg", "92.00"),
    ("SKU-206", "Ragi Flour 1kg", "72.00"),
    ("SKU-306", "Paneer 200g", "95.00"),
    ("SKU-307", "Cheese Slices 200g", "135.00"),
    ("SKU-308", "Curd 500g", "38.00"),
    ("SKU-309", "Milk 1L", "68.00"),
    ("SKU-310", "Ghee 500ml", "325.00"),
    ("SKU-423", "Groundnut Oil 1L", "178.00"),
    ("SKU-424", "Mustard Oil 1L", "165.00"),
    ("SKU-425", "Coconut Oil 500ml", "142.00"),
    ("SKU-426", "Olive Oil 500ml", "425.00"),
    ("SKU-519", "Filter Coffee 200g", "165.00"),
    ("SKU-520", "Instant Coffee 100g", "210.00"),
    ("SKU-521", "Green Tea 100 bags", "280.00"),
    ("SKU-601", "Parle-G Biscuits 800g", "100.00"),
    ("SKU-602", "Marie Biscuits 500g", "75.00"),
    ("SKU-603", "Potato Chips 150g", "40.00"),
    ("SKU-604", "Mixed Nuts 200g", "220.00"),
    ("SKU-605", "Tomato Ketchup 1kg", "125.00"),
    ("SKU-606", "Instant Noodles  pack of 12", "180.00"),
    ("SKU-607", "Dishwash Liquid 750ml", "115.00"),
    ("SKU-608", "Laundry Detergent 2kg", "245.00"),
]
PRODUCT_BY_SKU = {p[0]: p for p in PRODUCTS}
PAYMENT_MODES = ["UPI"] * 45 + ["CASH"] * 35 + ["CARD"] * 20


def money(value):
    """Format money to exactly two decimal places without floats."""
    return format(Decimal(value).quantize(Decimal("0.01")), ".2f")


def random_timestamp(rng, start_day, end_day):
    days = (end_day - start_day).days
    day = start_day + timedelta(days=rng.randint(0, days))
    seconds = rng.randint(8 * 3600, 21 * 3600 + 59 * 60 + 59)
    return datetime.combine(day, datetime.min.time()) + timedelta(seconds=seconds)


def make_sale(rng, transaction_id, when=None, store=None, product=None, quantity=None):
    product = product or rng.choice(PRODUCTS)
    return {
        "transaction_id": transaction_id,
        "store_code": store or rng.choice(STORES),
        "sold_at": (when or random_timestamp(
            rng, date(2026, 9, 1), date(2026, 10, 17)
        )).strftime("%Y-%m-%d %H:%M:%S"),
        "sku": product[0],
        "product_name": product[1],
        "quantity": quantity if quantity is not None else rng.randint(1, 6),
        "unit_price": product[2],
        "discount": "0.00",
        "payment_mode": rng.choice(PAYMENT_MODES),
        "original_transaction_id": "",
    }


def maybe_discount(rng, row):
    if rng.random() >= 0.70:
        gross = Decimal(row["unit_price"]) * abs(int(row["quantity"]))
        # A small discount, from 1% to 8%, rounded to cents and capped at gross.
        cents = int(gross * 100)
        discount_cents = max(1, min(cents, int(cents * rng.randint(1, 8) / 100)))
        row["discount"] = money(Decimal(discount_cents) / 100)
    return row


def generate_rows(rng, count, prefix, start_day, end_day):
    """Generate normal transactions with valid, quantity-limited returns."""
    rows = []
    available_sales = []
    remaining = {}
    for number in range(1, count + 1):
        make_return = bool(available_sales) and rng.random() < 0.04
        if make_return:
            original = rng.choice(available_sales)
            original_time = datetime.strptime(original["sold_at"], "%Y-%m-%d %H:%M:%S")
            latest = datetime.combine(end_day, datetime.max.time()).replace(microsecond=0)
            earliest = original_time + timedelta(seconds=1)
            if earliest > latest:
                make_return = False
            else:
                return_time = earliest + timedelta(
                    seconds=rng.randint(0, max(0, int((latest - earliest).total_seconds())))
                )
                qty = -rng.randint(1, remaining[original["transaction_id"]])
                row = {
                    "transaction_id": f"{prefix}-{number:06d}",
                    "store_code": original["store_code"],
                    "sold_at": return_time.strftime("%Y-%m-%d %H:%M:%S"),
                    "sku": original["sku"],
                    "product_name": original["product_name"],
                    "quantity": qty,
                    "unit_price": original["unit_price"],
                    "discount": "0.00",
                    "payment_mode": rng.choice(PAYMENT_MODES),
                    "original_transaction_id": original["transaction_id"],
                }
                remaining[original["transaction_id"]] += qty
                if remaining[original["transaction_id"]] == 0:
                    available_sales.remove(original)
                rows.append(row)
        if not make_return:
            when = random_timestamp(rng, start_day, end_day)
            row = maybe_discount(rng, make_sale(
                rng, f"{prefix}-{number:06d}", when=when
            ))
            rows.append(row)
            available_sales.append(row)
            remaining[row["transaction_id"]] = int(row["quantity"])
    # Return decisions replace rows, so the generated row count is exactly count.
    return rows


def write_csv(path, rows, header=HEADER, newline="\n", bom=False):
    path.parent.mkdir(parents=True, exist_ok=True)
    encoding = "utf-8-sig" if bom else "utf-8"
    with path.open("w", encoding=encoding, newline="") as handle:
        writer = csv.writer(handle, lineterminator=newline)
        writer.writerow(header)
        for row in rows:
            if isinstance(row, dict):
                writer.writerow([row.get(col, "") for col in header])
            else:
                writer.writerow(row)


def valid_small_rows(prefix, count, rng, start_day=date(2026, 10, 1),
                     end_day=date(2026, 10, 17)):
    rows = []
    for i in range(1, count + 1):
        when = random_timestamp(rng, start_day, end_day)
        rows.append(maybe_discount(rng, make_sale(rng, f"{prefix}-{i:03d}", when=when)))
    return rows


def generate_history(rng):
    rows = []
    available_sales = []
    remaining = {}
    number = 1
    for offset in range(14):
        day = date(2026, 10, 4) + timedelta(days=offset)
        daily_count = 190 if day.weekday() >= 5 else 150
        for _ in range(daily_count):
            if available_sales and rng.random() < 0.04:
                original = rng.choice(available_sales)
                original_time = datetime.strptime(original["sold_at"], "%Y-%m-%d %H:%M:%S")
                earliest = max(
                    original_time + timedelta(seconds=1),
                    datetime.combine(day, datetime.min.time()).replace(hour=8),
                )
                latest = datetime.combine(day, datetime.min.time()).replace(
                    hour=21, minute=59, second=59
                )
                if earliest <= latest:
                    seconds = rng.randint(0, int((latest - earliest).total_seconds()))
                    when = earliest + timedelta(seconds=seconds)
                    qty = -rng.randint(1, remaining[original["transaction_id"]])
                    row = {
                        "transaction_id": f"H-{number:06d}",
                        "store_code": original["store_code"],
                        "sold_at": when.strftime("%Y-%m-%d %H:%M:%S"),
                        "sku": original["sku"],
                        "product_name": original["product_name"],
                        "quantity": qty,
                        "unit_price": original["unit_price"],
                        "discount": "0.00",
                        "payment_mode": rng.choice(PAYMENT_MODES),
                        "original_transaction_id": original["transaction_id"],
                    }
                    remaining[original["transaction_id"]] += qty
                    if remaining[original["transaction_id"]] == 0:
                        available_sales.remove(original)
                    rows.append(row)
                    number += 1
                    continue
            store = rng.choice(STORES)
            seconds = rng.randint(8 * 3600, 21 * 3600 + 59 * 60 + 59)
            when = datetime.combine(day, datetime.min.time()) + timedelta(seconds=seconds)
            row = maybe_discount(rng, make_sale(
                rng, f"H-{number:06d}", when=when, store=store
            ))
            rows.append(row)
            available_sales.append(row)
            remaining[row["transaction_id"]] = int(row["quantity"])
            number += 1
    return rows


def generate_sales_20k(rng):
    return generate_rows(
        rng, 20000, "B",
        date(2026, 9, 1), date(2026, 9, 30)
    )


def generate_with_bom(rng):
    rows = valid_small_rows("BOM", 10, rng)
    write_csv(DATA_DIR / "with_bom.csv", rows, bom=True)
    return len(rows)


def generate_crlf(rng):
    rows = valid_small_rows("CRLF", 10, rng)
    write_csv(DATA_DIR / "crlf.csv", rows, newline="\r\n")
    return len(rows)


def generate_qty_zero(rng):
    rows = valid_small_rows("Z", 10, rng)
    for index in (3, 7):
        rows[index]["quantity"] = 0
    write_csv(DATA_DIR / "qty_zero.csv", rows)
    return len(rows)


def generate_return_before_original(rng):
    # The first row references RBO-003, which appears later in the file.
    sale_2 = make_sale(
        rng, "RBO-002", when=datetime(2026, 10, 10, 10, 0, 0),
        store="ST01", product=PRODUCTS[0], quantity=2
    )
    original = make_sale(
        rng, "RBO-003", when=datetime(2026, 10, 10, 11, 0, 0),
        store="ST01", product=PRODUCTS[0], quantity=3
    )
    first_return = {
        **original, "transaction_id": "RBO-001",
        "sold_at": "2026-10-11 10:00:00", "quantity": -1,
        "discount": "0.00", "original_transaction_id": "RBO-003",
    }
    extras = valid_small_rows("RBO", 3, rng)
    # Rename extra IDs so all six IDs follow the RBO-001...RBO-006 pattern.
    for i, row in enumerate(extras, start=4):
        row["transaction_id"] = f"RBO-{i:03d}"
    rows = [first_return, sale_2, original] + extras
    write_csv(DATA_DIR / "return_before_original.csv", rows)
    return len(rows)


def generate_return_exceeds_part1(rng):
    sale = make_sale(
        rng, "RE-001", when=datetime(2026, 10, 10, 10, 0, 0),
        store="ST02", product=PRODUCTS[1], quantity=3
    )
    extras = valid_small_rows("RE", 4, rng)
    for i, row in enumerate(extras, start=2):
        row["transaction_id"] = f"RE-{i:03d}"
    rows = [sale] + extras
    write_csv(DATA_DIR / "return_exceeds_part1.csv", rows)
    return len(rows)


def generate_return_exceeds_part2(rng):
    base = {
        "store_code": "ST02", "sku": PRODUCTS[1][0],
        "product_name": PRODUCTS[1][1], "unit_price": PRODUCTS[1][2],
        "discount": "0.00", "payment_mode": "UPI",
        "original_transaction_id": "RE-001",
    }
    returns = [
        {**base, "transaction_id": "RE2-001", "sold_at": "2026-10-11 10:00:00",
         "quantity": -2},
        {**base, "transaction_id": "RE2-002", "sold_at": "2026-10-12 10:00:00",
         "quantity": -2},
    ]
    extras = valid_small_rows("RE2", 3, rng)
    for i, row in enumerate(extras, start=3):
        row["transaction_id"] = f"RE2-{i:03d}"
    rows = returns + extras
    write_csv(DATA_DIR / "return_exceeds_part2.csv", rows)
    return len(rows)


def generate_same_rows_renamed(rng):
    # Reuse the exact BOM fixture rows, but write them in reverse order without a BOM.
    source = DATA_DIR / "with_bom.csv"
    with source.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    rows.reverse()
    write_csv(DATA_DIR / "same_rows_renamed.csv", rows)
    return len(rows)


def generate_bad_header(rng):
    rows = valid_small_rows("BH", 10, rng)
    bad_header = [column for column in HEADER if column != "unit_price"]
    write_csv(DATA_DIR / "bad_header.csv", rows, header=bad_header)
    return len(rows)


def generate_mixed_errors(rng):
    rows = valid_small_rows("M", 20, rng)
    # Exactly one instance of each requested problem; row IDs remain M-001..M-020
    rows[0]["store_code"] = "ST99"
    rows[1]["sold_at"] = "2027-01-01 10:00:00"
    rows[2]["sold_at"] = "17/10/2026 10:00"
    rows[3]["quantity"] = "1.5"
    rows[4]["unit_price"] = "-10.00"
    rows[5]["discount"] = money(
        Decimal(rows[5]["unit_price"]) * Decimal(int(rows[5]["quantity"])) + Decimal("1.00")
    )
    rows[6]["payment_mode"] = "WALLET"
    rows[7]["quantity"] = -1
    rows[7]["original_transaction_id"] = "MISSING-ORIGINAL"
    rows[9]["transaction_id"] = rows[8]["transaction_id"]  # duplicate a valid earlier row
    write_csv(DATA_DIR / "mixed_errors.csv", rows)
    return len(rows)


def generate_history_file(rng):
    rows = generate_history(rng)
    write_csv(DATA_DIR / "history_14days.csv", rows)
    return len(rows)


def generate_sales_file(rng):
    rows = generate_sales_20k(rng)
    write_csv(DATA_DIR / "sales_20k.csv", rows)
    return len(rows)


def ensure_sample():
    if not SAMPLE_PATH.exists():
        SAMPLE_PATH.parent.mkdir(parents=True, exist_ok=True)
        with (DATA_DIR / "history_14days.csv").open(
            "r", encoding="utf-8", newline=""
        ) as source, SAMPLE_PATH.open("w", encoding="utf-8", newline="") as target:
            for index, line in enumerate(source):
                if index >= 51:  # header plus 50 data rows
                    break
                target.write(line)
        return True
    return False


def main():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    rng = random.Random(SEED)

    results = []
    # Keep this generation order aligned with the requested import order.
    results.append(("history_14days.csv", generate_history_file(rng), "all", 0))
    results.append(("sales_20k.csv", generate_sales_file(rng), "all", 0))
    results.append(("with_bom.csv", generate_with_bom(rng), 10, 0))
    results.append(("crlf.csv", generate_crlf(rng), 10, 0))
    results.append(("qty_zero.csv", generate_qty_zero(rng), 8, 2))
    results.append(("return_before_original.csv", generate_return_before_original(rng), 5, 1))
    results.append(("return_exceeds_part1.csv", generate_return_exceeds_part1(rng), 5, 0))
    results.append(("return_exceeds_part2.csv", generate_return_exceeds_part2(rng), 4, 1))
    results.append(("same_rows_renamed.csv", generate_same_rows_renamed(rng), 0, 10))
    results.append(("bad_header.csv", generate_bad_header(rng), 0, 10))
    results.append(("mixed_errors.csv", generate_mixed_errors(rng), 11, 9))
    sample_created = ensure_sample()

    print(f"{'filename':30} {'rows written':>12} {'expected accepted':>18} {'expected rejected':>18}")
    print("-" * 82)
    for filename, written, accepted, rejected in results:
        accepted_text = str(accepted) if accepted != "all" else str(written)
        rejected_text = str(rejected)
        print(f"{filename:30} {written:12d} {accepted_text:>18} {rejected_text:>18}")
    print(f"\nGenerated CSV files in: {DATA_DIR}")
    print(f"Sample file: {SAMPLE_PATH} ({'created' if sample_created else 'kept existing file'})")


if __name__ == "__main__":
    main()
