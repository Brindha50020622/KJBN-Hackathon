from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from decimal import ROUND_HALF_UP, Decimal

from app.rules import IST

MIN_DATE = date(2000, 1, 1)
MAX_DATE = date(2100, 12, 31)
PAYMENT_ORDER = ["CASH", "UPI", "CARD"]


@dataclass(frozen=True)
class StoreTotals:
    code: str
    name: str
    revenue_paise: int
    transactions: int
    sold_quantity: int
    returned_quantity: int


def ist_range_to_utc(
    date_from: date | None, date_to: date | None
) -> tuple[datetime | None, datetime | None]:
    """IST calendar dates, both ends included, as a UTC range [start, end)."""
    for value in (date_from, date_to):
        if value is not None and not MIN_DATE <= value <= MAX_DATE:
            raise ValueError("date must be between 2000-01-01 and 2100-12-31")
    if date_from and date_to and date_from > date_to:
        raise ValueError("date_from must not be after date_to")
    start = datetime.combine(date_from, time.min, tzinfo=IST).astimezone(UTC) if date_from else None
    end = (
        datetime.combine(date_to + timedelta(days=1), time.min, tzinfo=IST).astimezone(UTC)
        if date_to
        else None
    )
    return start, end


def return_rate_percent(returned: int, sold: int) -> float:
    """Returned units as a percent of sold units. 0 when nothing was sold."""
    if sold <= 0:
        return 0.0
    rate = Decimal(returned) * 100 / Decimal(sold)
    return float(rate.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def complete_payment_split(found: dict[str, tuple[int, int]]) -> list[tuple[str, int, int]]:
    """found: mode -> (revenue_paise, transactions). Always lists all three modes."""
    return [(mode, *found.get(mode, (0, 0))) for mode in PAYMENT_ORDER]
