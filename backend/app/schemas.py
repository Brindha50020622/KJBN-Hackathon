from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models import ImportBatch


class BatchOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    filename: str
    uploaded_at: datetime
    file_hash: str
    rows_total: int
    rows_accepted: int
    rows_rejected: int
    status: str
    error_report_url: str | None = None


class BatchPage(BaseModel):
    items: list[BatchOut]
    total: int
    limit: int
    offset: int


def to_batch_out(batch: ImportBatch) -> BatchOut:
    out = BatchOut.model_validate(batch)
    if batch.rows_rejected > 0 or batch.status == "REJECTED":
        out.error_report_url = f"/api/v1/batches/{batch.id}/errors.csv"
    return out
