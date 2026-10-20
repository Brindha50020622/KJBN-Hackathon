import logging
from collections import Counter
from datetime import datetime

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app import repository as repo
from app.config import settings
from app.db import SessionLocal
from app.importer import ParsedFile, file_hash, import_file, parse_csv, plan_products
from app.logging_setup import request_id_var
from app.models import ImportBatch
from app.rules import HeaderError

log = logging.getLogger("app.import")


def register_upload(filename: str, raw: bytes) -> tuple[ImportBatch, bool]:
    """Create the batch row. Returns (batch, should_process).

    The unique file_hash makes this safe when the same file arrives twice at once:
    one insert wins, the other gets nothing back and is reported as a duplicate.
    A batch that FAILED earlier is claimed again, so the same file can be retried.
    """
    digest = file_hash(raw)
    with SessionLocal.begin() as session:
        batch_id = session.execute(
            pg_insert(ImportBatch)
            .values(filename=filename, file_hash=digest, status="PROCESSING")
            .on_conflict_do_nothing(index_elements=["file_hash"])
            .returning(ImportBatch.id)
        ).scalar()
        if batch_id is not None:
            return session.get(ImportBatch, batch_id), True

        existing = session.execute(
            select(ImportBatch).where(ImportBatch.file_hash == digest)
        ).scalar_one()
        claimed = session.execute(
            update(ImportBatch)
            .where(ImportBatch.id == existing.id, ImportBatch.status == "FAILED")
            .values(status="PROCESSING")
            .returning(ImportBatch.id)
        ).scalar()
        session.refresh(existing)
        return existing, claimed is not None


def process_batch(batch_id: int, raw: bytes, now: datetime, request_id: str) -> None:
    """Background job. Any unexpected error marks the batch FAILED and nothing is half-written."""
    request_id_var.set(request_id)
    try:
        _run_import(batch_id, raw, now)
    except Exception:
        log.exception("import failed", extra={"batch_id": batch_id})
        with SessionLocal.begin() as session:
            session.execute(
                update(ImportBatch).where(ImportBatch.id == batch_id).values(status="FAILED")
            )


def _reject_file(batch_id: int, reason: str) -> None:
    with SessionLocal.begin() as session:
        repo.insert_errors(session, batch_id, [(1, "header", reason)], settings.insert_chunk_size)
        repo.finish_batch(session, batch_id, "REJECTED", 0, 0, 0)
    log.warning("file rejected", extra={"batch_id": batch_id, "reason": reason})


def _referenced_ids(parsed: ParsedFile) -> tuple[set[str], set[str]]:
    ids = {row["transaction_id"] for _, row in parsed.rows}
    originals = {
        row["original_transaction_id"] for _, row in parsed.rows if row["original_transaction_id"]
    }
    return ids | originals, originals


def _run_import(batch_id: int, raw: bytes, now: datetime) -> None:
    try:
        parsed = parse_csv(raw)
    except HeaderError as exc:
        _reject_file(batch_id, str(exc))
        return

    all_ids, originals = _referenced_ids(parsed)
    chunk = settings.insert_chunk_size

    with SessionLocal.begin() as session:
        repo.lock_imports(session)
        stores = repo.store_ids(session)
        known = repo.load_known(session, all_ids)
        returned = repo.load_returned_qty(session, originals)

        result = import_file(raw, set(stores), now, known, returned)
        accepted = result.accepted

        names = repo.load_product_names(session, {t.sku for t in accepted})
        new_products, aliases = plan_products(names, accepted)
        repo.insert_products(session, new_products)
        repo.insert_aliases(session, aliases)
        repo.insert_transactions(session, accepted, stores, batch_id, chunk)
        repo.insert_errors(
            session, batch_id, [(i.row_number, i.column, i.message) for i in result.issues], chunk
        )
        repo.finish_batch(
            session, batch_id, "COMPLETED", result.rows_total, len(accepted), result.rows_rejected
        )

    log.info(
        "import finished",
        extra={
            "batch_id": batch_id,
            "rows_total": result.rows_total,
            "rows_accepted": len(accepted),
            "rows_rejected": result.rows_rejected,
        },
    )
    if result.issues:
        reasons = Counter(f"{i.column}: {i.message}" for i in result.issues)
        log.warning(
            "rows rejected",
            extra={
                "batch_id": batch_id,
                "rows_rejected": result.rows_rejected,
                "top_reasons": dict(reasons.most_common(5)),
            },
        )


def mark_stale_imports_failed() -> None:
    """At startup, an import still PROCESSING was cut off by a restart."""
    try:
        with SessionLocal.begin() as session:
            count = session.execute(
                update(ImportBatch)
                .where(ImportBatch.status == "PROCESSING")
                .values(status="FAILED")
            ).rowcount
        if count:
            log.warning("marked unfinished imports as failed", extra={"count": count})
    except Exception:
        log.exception("could not check unfinished imports")
