from collections.abc import Iterator, Sequence

from sqlalchemy import func, insert, select, text, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.importer import NewTransaction
from app.models import ImportBatch, ImportRowError, Product, ProductAlias, Store, Transaction
from app.rules import TxnInfo

IMPORT_LOCK_KEY = 5001
LOOKUP_CHUNK = 5000


def _chunks(items: Sequence, size: int) -> Iterator[Sequence]:
    for start in range(0, len(items), size):
        yield items[start : start + size]


def lock_imports(session: Session) -> None:
    """Only one import runs at a time. The lock is released when the transaction ends."""
    session.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": IMPORT_LOCK_KEY})


def store_ids(session: Session) -> dict[str, int]:
    return {code: id_ for code, id_ in session.execute(select(Store.code, Store.id)).all()}


def load_known(session: Session, ids: set[str]) -> dict[str, TxnInfo]:
    known: dict[str, TxnInfo] = {}
    for chunk in _chunks(sorted(ids), LOOKUP_CHUNK):
        rows = session.execute(
            select(
                Transaction.transaction_id,
                Store.code,
                Transaction.sku,
                Transaction.quantity,
                Transaction.sold_at,
            )
            .join(Store, Store.id == Transaction.store_id)
            .where(Transaction.transaction_id.in_(chunk))
        ).all()
        for row in rows:
            known[row[0]] = TxnInfo(*row)
    return known


def load_returned_qty(session: Session, originals: set[str]) -> dict[str, int]:
    returned: dict[str, int] = {}
    for chunk in _chunks(sorted(originals), LOOKUP_CHUNK):
        rows = session.execute(
            select(Transaction.original_transaction_id, func.sum(-Transaction.quantity))
            .where(Transaction.original_transaction_id.in_(chunk), Transaction.is_return)
            .group_by(Transaction.original_transaction_id)
        ).all()
        for original_id, total in rows:
            returned[original_id] = int(total)
    return returned


def load_product_names(session: Session, skus: set[str]) -> dict[str, str]:
    names: dict[str, str] = {}
    for chunk in _chunks(sorted(skus), LOOKUP_CHUNK):
        for sku, name in session.execute(
            select(Product.sku, Product.name).where(Product.sku.in_(chunk))
        ).all():
            names[sku] = name
    return names


def insert_products(session: Session, new_products: dict[str, str]) -> None:
    if new_products:
        session.execute(
            insert(Product), [{"sku": sku, "name": name} for sku, name in new_products.items()]
        )


def insert_aliases(session: Session, aliases: set[tuple[str, str]]) -> None:
    if not aliases:
        return
    ids = dict(
        session.execute(
            select(Product.sku, Product.id).where(Product.sku.in_({sku for sku, _ in aliases}))
        ).all()
    )
    stmt = pg_insert(ProductAlias).on_conflict_do_nothing(constraint="uq_alias_per_product")
    session.execute(stmt, [{"product_id": ids[sku], "alias": alias} for sku, alias in aliases])


def insert_transactions(
    session: Session,
    transactions: list[NewTransaction],
    store_map: dict[str, int],
    batch_id: int,
    chunk_size: int,
) -> None:
    for chunk in _chunks(transactions, chunk_size):
        session.execute(
            insert(Transaction),
            [
                {
                    "transaction_id": t.transaction_id,
                    "batch_id": batch_id,
                    "store_id": store_map[t.store_code],
                    "sold_at": t.sold_at,
                    "sku": t.sku,
                    "product_name": t.product_name,
                    "quantity": t.quantity,
                    "unit_price_paise": t.unit_price_paise,
                    "discount_paise": t.discount_paise,
                    "line_total_paise": t.line_total_paise,
                    "payment_mode": t.payment_mode,
                    "original_transaction_id": t.original_transaction_id,
                    "is_return": t.is_return,
                }
                for t in chunk
            ],
        )


def insert_errors(
    session: Session, batch_id: int, errors: list[tuple[int, str, str]], chunk_size: int
) -> None:
    for chunk in _chunks(errors, chunk_size):
        session.execute(
            insert(ImportRowError),
            [
                {"batch_id": batch_id, "row_number": number, "column_name": column, "message": msg}
                for number, column, msg in chunk
            ],
        )


def finish_batch(
    session: Session, batch_id: int, status: str, total: int, accepted: int, rejected: int
) -> None:
    session.execute(
        update(ImportBatch)
        .where(ImportBatch.id == batch_id)
        .values(status=status, rows_total=total, rows_accepted=accepted, rows_rejected=rejected)
    )


def list_batches(session: Session, limit: int, offset: int) -> tuple[list[ImportBatch], int]:
    total = session.scalar(select(func.count()).select_from(ImportBatch)) or 0
    items = session.scalars(
        select(ImportBatch).order_by(ImportBatch.id.desc()).limit(limit).offset(offset)
    ).all()
    return list(items), total


def list_errors(session: Session, batch_id: int) -> list[tuple[int, str, str]]:
    rows = session.execute(
        select(ImportRowError.row_number, ImportRowError.column_name, ImportRowError.message)
        .where(ImportRowError.batch_id == batch_id)
        .order_by(ImportRowError.row_number, ImportRowError.id)
    ).all()
    return [(r[0], r[1], r[2]) for r in rows]
