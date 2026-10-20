from datetime import date, datetime

from pydantic import BaseModel, ConfigDict

from app.models import ImportBatch, Transaction
from app.rules import IST


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


class TransactionOut(BaseModel):
    transaction_id: str
    batch_id: int
    store_code: str
    sold_at: datetime
    sold_at_ist: str
    sku: str
    product_name: str
    quantity: int
    unit_price_paise: int
    discount_paise: int
    line_total_paise: int
    payment_mode: str
    original_transaction_id: str | None
    is_return: bool


class TransactionPage(BaseModel):
    items: list[TransactionOut]
    total: int
    limit: int
    offset: int


def to_transaction_out(txn: Transaction, store_code: str) -> TransactionOut:
    return TransactionOut(
        transaction_id=txn.transaction_id,
        batch_id=txn.batch_id,
        store_code=store_code,
        sold_at=txn.sold_at,
        sold_at_ist=txn.sold_at.astimezone(IST).strftime("%Y-%m-%d %H:%M:%S"),
        sku=txn.sku,
        product_name=txn.product_name,
        quantity=txn.quantity,
        unit_price_paise=txn.unit_price_paise,
        discount_paise=txn.discount_paise,
        line_total_paise=txn.line_total_paise,
        payment_mode=txn.payment_mode,
        original_transaction_id=txn.original_transaction_id,
        is_return=txn.is_return,
    )


class DayRevenue(BaseModel):
    day: date
    revenue_paise: int


class StoreRevenue(BaseModel):
    store_code: str
    store_name: str
    revenue_paise: int
    transactions: int


class ProductNet(BaseModel):
    sku: str
    name: str
    net_quantity: int
    revenue_paise: int


class StoreReturnRate(BaseModel):
    store_code: str
    store_name: str
    sold_quantity: int
    returned_quantity: int
    return_rate_percent: float


class PaymentShare(BaseModel):
    payment_mode: str
    revenue_paise: int
    transactions: int


class DashboardOut(BaseModel):
    date_from: date | None
    date_to: date | None
    total_revenue_paise: int
    total_transactions: int
    revenue_by_day: list[DayRevenue]
    revenue_by_store: list[StoreRevenue]
    top_products: list[ProductNet]
    return_rate_by_store: list[StoreReturnRate]
    payment_split: list[PaymentShare]
