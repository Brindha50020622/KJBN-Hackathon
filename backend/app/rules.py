import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta, timezone

REQUIRED_COLUMNS = [
    "transaction_id",
    "store_code",
    "sold_at",
    "sku",
    "product_name",
    "quantity",
    "unit_price",
    "discount",
    "payment_mode",
    "original_transaction_id",
]
PAYMENT_MODES = {"CASH", "UPI", "CARD"}
MAX_LENGTHS = {"transaction_id": 50, "sku": 50, "product_name": 200}
MAX_QUANTITY = 100_000
MAX_AMOUNT_PAISE = 1_000_000_000  # 10,000,000.00

IST = timezone(timedelta(hours=5, minutes=30))
_INT = re.compile(r"^-?[0-9]+$")
_MONEY = re.compile(r"^[0-9]+(\.[0-9]{1,2})?$")
_DATETIME = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2} [0-9]{2}:[0-9]{2}:[0-9]{2}$")


class HeaderError(Exception):
    """Header is missing or has missing columns. Rejects the whole file."""


@dataclass(frozen=True)
class RowError:
    column: str
    message: str


@dataclass(frozen=True)
class TxnInfo:
    transaction_id: str
    store_code: str
    sku: str
    quantity: int
    sold_at: datetime


def validate_header(columns: list[str]) -> None:
    missing = [c for c in REQUIRED_COLUMNS if c not in columns]
    if missing:
        raise HeaderError(f"missing columns: {', '.join(missing)}")


def parse_money_to_paise(text: str) -> int:
    text = text.strip()
    if not _MONEY.match(text):
        raise ValueError("must be a non-negative amount with at most 2 decimals")
    whole, _, fraction = text.partition(".")
    return int(whole) * 100 + int(fraction.ljust(2, "0") or 0)


def parse_sold_at(text: str) -> datetime:
    """Parse 'YYYY-MM-DD HH:MM:SS' as IST and return an aware UTC datetime."""
    text = text.strip()
    if not _DATETIME.match(text):
        raise ValueError("must be YYYY-MM-DD HH:MM:SS")
    try:
        local = datetime.strptime(text, "%Y-%m-%d %H:%M:%S").replace(tzinfo=IST)
        return local.astimezone(UTC)
    except OverflowError as exc:
        raise ValueError("date is out of range") from exc


def line_total_paise(quantity: int, unit_price_paise: int, discount_paise: int) -> int:
    """Sale: qty*price - discount. Return: the discount is given back (assumption 9)."""
    sign = 1 if quantity > 0 else -1
    return quantity * unit_price_paise - sign * discount_paise


def validate_row(row: dict[str, str], store_codes: set[str], now: datetime) -> list[RowError]:
    errors: list[RowError] = []

    def fail(column: str, message: str) -> None:
        errors.append(RowError(column, message))

    def money(column: str) -> int | None:
        try:
            value = parse_money_to_paise(row.get(column, ""))
        except ValueError as exc:
            fail(column, str(exc))
            return None
        if value > MAX_AMOUNT_PAISE:
            fail(column, "is too large")
            return None
        return value

    def text(column: str) -> str:
        return row.get(column, "").strip()

    if not text("transaction_id"):
        fail("transaction_id", "is required")
    if text("store_code") not in store_codes:
        fail("store_code", "unknown store code")
    try:
        if parse_sold_at(text("sold_at")) > now:
            fail("sold_at", "is in the future")
    except ValueError as exc:
        fail("sold_at", str(exc))
    if not text("sku"):
        fail("sku", "is required")
    if not text("product_name"):
        fail("product_name", "is required")

    for column, value in row.items():
        if "\x00" in value:
            fail(column, "contains an invalid character")
    for column, limit in MAX_LENGTHS.items():
        if len(text(column)) > limit:
            fail(column, f"is longer than {limit} characters")

    quantity = None
    raw_quantity = text("quantity")
    if not _INT.match(raw_quantity):
        fail("quantity", "must be a whole number")
    elif len(raw_quantity) > 9 or abs(int(raw_quantity)) > MAX_QUANTITY:
        fail("quantity", "is too large")
    elif int(raw_quantity) == 0:
        fail("quantity", "must not be zero")
    else:
        quantity = int(raw_quantity)

    unit_price = money("unit_price")
    discount = money("discount")
    if quantity is not None and unit_price is not None and discount is not None:
        if discount > abs(quantity) * unit_price:
            fail("discount", "is more than quantity x unit_price")

    if text("payment_mode") not in PAYMENT_MODES:
        fail("payment_mode", "must be CASH, UPI or CARD")

    original = text("original_transaction_id")
    if quantity is not None:
        if quantity < 0 and not original:
            fail("original_transaction_id", "is required for a return")
        if quantity > 0 and original:
            fail("original_transaction_id", "must be empty for a sale")
    return errors


def check_return(
    quantity: int,
    store_code: str,
    sku: str,
    sold_at: datetime,
    original: TxnInfo | None,
    already_returned: int,
) -> RowError | None:
    column = "original_transaction_id"
    if original is None:
        return RowError(column, "original transaction not found")
    if original.quantity < 0:
        return RowError(column, "cannot return a return")
    if original.store_code != store_code:
        return RowError(column, "original is from a different store")
    if original.sku != sku:
        return RowError(column, "original has a different sku")
    if sold_at < original.sold_at:
        return RowError(column, "return is dated before the original sale")
    if already_returned + abs(quantity) > original.quantity:
        return RowError("quantity", "total returned quantity is more than the original quantity")
    return None
