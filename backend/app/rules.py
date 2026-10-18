from dataclasses import dataclass
from datetime import datetime

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
    raise NotImplementedError


def parse_money_to_paise(text: str) -> int:
    raise NotImplementedError


def parse_sold_at(text: str) -> datetime:
    """Parse 'YYYY-MM-DD HH:MM:SS' as IST and return an aware UTC datetime."""
    raise NotImplementedError


def line_total_paise(quantity: int, unit_price_paise: int, discount_paise: int) -> int:
    raise NotImplementedError


def validate_row(row: dict[str, str], store_codes: set[str], now: datetime) -> list[RowError]:
    raise NotImplementedError


def check_return(
    quantity: int,
    store_code: str,
    sku: str,
    sold_at: datetime,
    original: TxnInfo | None,
    already_returned: int,
) -> RowError | None:
    raise NotImplementedError