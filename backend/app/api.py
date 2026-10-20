import csv
import io
import logging
from datetime import datetime
from typing import Annotated

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    Path,
    Query,
    Request,
    Response,
    UploadFile,
)
from sqlalchemy.orm import Session

from app import repository as repo
from app.clock import get_now
from app.config import settings
from app.db import SessionLocal
from app.errors import DuplicateFileError, FileTooLargeError, NotFoundError
from app.models import ImportBatch
from app.schemas import BatchOut, BatchPage, to_batch_out
from app.service import process_batch, register_upload

log = logging.getLogger("app.api")
router = APIRouter(prefix="/api/v1", tags=["batches"])

BatchId = Annotated[int, Path(ge=1, le=2_147_483_647)]


def get_session():
    with SessionLocal() as session:
        yield session


DbSession = Annotated[Session, Depends(get_session)]


def _get_batch(session: Session, batch_id: int) -> ImportBatch:
    batch = session.get(ImportBatch, batch_id)
    if batch is None:
        raise NotFoundError(f"Batch {batch_id} not found")
    return batch


@router.post("/batches", status_code=202, response_model=BatchOut)
def upload_batch(
    background_tasks: BackgroundTasks,
    request: Request,
    file: Annotated[UploadFile, File()],
    now: Annotated[datetime, Depends(get_now)],
):
    max_bytes = settings.max_upload_mb * 1024 * 1024
    raw = file.file.read(max_bytes + 1)
    if len(raw) > max_bytes:
        raise FileTooLargeError(f"File is larger than {settings.max_upload_mb} MB")

    filename = (file.filename or "upload.csv")[:255]
    batch, should_process = register_upload(filename, raw)
    if not should_process:
        log.warning("duplicate file upload", extra={"batch_id": batch.id, "upload_name": filename})
        raise DuplicateFileError(
            "This file was already uploaded",
            details={"batch_id": batch.id, "status": batch.status},
        )

    background_tasks.add_task(process_batch, batch.id, raw, now, request.state.request_id)
    log.info(
        "upload accepted",
        extra={
            "batch_id": batch.id,
            "upload_name": filename,
            "bytes": len(raw),
        },
    )
    return to_batch_out(batch)


@router.get("/batches", response_model=BatchPage)
def list_batches(
    session: DbSession,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0, le=10_000_000)] = 0,
):
    items, total = repo.list_batches(session, limit, offset)
    return BatchPage(
        items=[to_batch_out(b) for b in items], total=total, limit=limit, offset=offset
    )


@router.get("/batches/{batch_id}", response_model=BatchOut)
def get_batch(batch_id: BatchId, session: DbSession):
    return to_batch_out(_get_batch(session, batch_id))


@router.get("/batches/{batch_id}/errors.csv")
def download_error_report(batch_id: BatchId, session: DbSession):
    _get_batch(session, batch_id)
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["row_number", "column", "message"])
    writer.writerows(repo.list_errors(session, batch_id))
    return Response(
        content=buffer.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="batch-{batch_id}-errors.csv"'},
    )
