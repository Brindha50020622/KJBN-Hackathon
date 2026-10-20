import csv
import hashlib
import io
from dataclasses import dataclass
from datetime import datetime

from app.rules import (
    HeaderError,
    TxnInfo,
    check_return,
    line_total_paise,
    parse_money_to_paise,
    parse_sold_at,
    validate_header,
    validate_row,
)


@dataclass(frozen=True)
class RowIssue:
    row_number: int  # header is row 1, first data row is row 2
    column: str
    message: str


@dataclass(frozen=True)
class NewTransaction:
    row_number: int
    transaction_id: str
    store_code: str
    sold_at: datetime
    sku: str
    product_name: str
    quantity: int
    unit_price_paise: int
    discount_paise: int
    line_total_paise: int
    payment_mode: str
    original_transaction_id: str | None
    is_return: bool


@dataclass(frozen=True)
class ParsedFile:
    rows: list[tuple[int, dict[str, str]]]
    issues: list[RowIssue]
    rows_total: int


@dataclass(frozen=True)
class ImportResult:
    rows_total: int
    accepted: list[NewTransaction]  # sales first, then returns: safe insert order
    issues: list[RowIssue]

    @property
    def rows_rejected(self) -> int:
        return len({i.row_number for i in self.issues})


def file_hash(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def parse_csv(raw: bytes) -> ParsedFile:
    try:
        text = raw.decode("utf-8-sig")  # also removes a BOM
    except UnicodeDecodeError as exc:
        raise HeaderError("file is not valid UTF-8") from exc

    rows: list[tuple[int, dict[str, str]]] = []
    issues: list[RowIssue] = []
    total = 0
    try:
        reader = csv.reader(io.StringIO(text, newline=""))  # handles CRLF
        header = [h.strip() for h in next(reader, [])]
        validate_header(header)
        for number, values in enumerate(reader, start=2):
            if not any(v.strip() for v in values):
                continue
            total += 1
            if len(values) != len(header):
                message = f"expected {len(header)} columns, found {len(values)}"
                issues.append(RowIssue(number, "row", message))
                continue
            rows.append((number, {h: v.strip() for h, v in zip(header, values, strict=True)}))
    except csv.Error as exc:
        raise HeaderError(f"file is not valid CSV: {exc}") from exc
    return ParsedFile(rows, issues, total)


def _build(number: int, row: dict[str, str]) -> NewTransaction:
    quantity = int(row["quantity"])
    price = parse_money_to_paise(row["unit_price"])
    discount = parse_money_to_paise(row["discount"])
    return NewTransaction(
        row_number=number,
        transaction_id=row["transaction_id"],
        store_code=row["store_code"],
        sold_at=parse_sold_at(row["sold_at"]),
        sku=row["sku"],
        product_name=row["product_name"],
        quantity=quantity,
        unit_price_paise=price,
        discount_paise=discount,
        line_total_paise=line_total_paise(quantity, price, discount),
        payment_mode=row["payment_mode"],
        original_transaction_id=row["original_transaction_id"] or None,
        is_return=quantity < 0,
    )


def _info(txn: NewTransaction) -> TxnInfo:
    return TxnInfo(txn.transaction_id, txn.store_code, txn.sku, txn.quantity, txn.sold_at)


def import_file(
    raw: bytes,
    store_codes: set[str],
    now: datetime,
    known: dict[str, TxnInfo],
    returned_qty: dict[str, int],
) -> ImportResult:
    """known: transactions already in the database.
    returned_qty: units already returned per original.
    """
    parsed = parse_csv(raw)
    issues = list(parsed.issues)
    sales: list[NewTransaction] = []
    returns: list[NewTransaction] = []

    for number, row in parsed.rows:
        errors = validate_row(row, store_codes, now)
        if errors:
            issues.extend(RowIssue(number, e.column, e.message) for e in errors)
            continue
        txn = _build(number, row)
        (returns if txn.is_return else sales).append(txn)

    accepted: list[NewTransaction] = []
    seen_in_file: set[str] = set()
    lookup = dict(known)
    returned = dict(returned_qty)

    def is_duplicate(txn: NewTransaction) -> bool:
        if txn.transaction_id in known:
            issues.append(RowIssue(txn.row_number, "transaction_id", "already imported"))
            return True
        if txn.transaction_id in seen_in_file:
            issues.append(RowIssue(txn.row_number, "transaction_id", "repeated in this file"))
            return True
        return False

    for txn in sales:
        if is_duplicate(txn):
            continue
        seen_in_file.add(txn.transaction_id)
        lookup[txn.transaction_id] = _info(txn)
        accepted.append(txn)

    # Returns are checked after all sales, so a return may come before its original in the file.
    for txn in returns:
        if is_duplicate(txn):
            continue
        original_id = txn.original_transaction_id or ""
        problem = check_return(
            txn.quantity,
            txn.store_code,
            txn.sku,
            txn.sold_at,
            lookup.get(original_id),
            returned.get(original_id, 0),
        )
        if problem:
            issues.append(RowIssue(txn.row_number, problem.column, problem.message))
            continue
        returned[original_id] = returned.get(original_id, 0) + abs(txn.quantity)
        seen_in_file.add(txn.transaction_id)
        lookup[txn.transaction_id] = _info(txn)
        accepted.append(txn)

    issues.sort(key=lambda i: i.row_number)
    return ImportResult(parsed.rows_total, accepted, issues)


def plan_products(
    existing: dict[str, str], accepted: list[NewTransaction]
) -> tuple[dict[str, str], set[tuple[str, str]]]:
    """First name seen for a sku wins. Later different names become aliases."""
    names = dict(existing)
    new_products: dict[str, str] = {}
    aliases: set[tuple[str, str]] = set()
    for txn in accepted:
        if txn.sku not in names:
            names[txn.sku] = txn.product_name
            new_products[txn.sku] = txn.product_name
        elif names[txn.sku] != txn.product_name:
            aliases.add((txn.sku, txn.product_name))
    return new_products, aliases
