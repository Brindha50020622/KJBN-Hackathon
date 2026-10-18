from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class Store(Base):
    __tablename__ = "stores"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(20), unique=True)
    name: Mapped[str] = mapped_column(String(100))
    city: Mapped[str] = mapped_column(String(100))


class Product(Base):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(primary_key=True)
    sku: Mapped[str] = mapped_column(String(50), unique=True)
    name: Mapped[str] = mapped_column(String(200))


class ProductAlias(Base):
    __tablename__ = "product_aliases"
    __table_args__ = (UniqueConstraint("product_id", "alias", name="uq_alias_per_product"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"))
    alias: Mapped[str] = mapped_column(String(200))


class ImportBatch(Base):
    __tablename__ = "import_batches"
    __table_args__ = (
        CheckConstraint(
            "status IN ('PROCESSING','COMPLETED','REJECTED','FAILED')", name="ck_batch_status"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    filename: Mapped[str] = mapped_column(String(255))
    uploaded_at: Mapped[datetime] = mapped_column(
    DateTime(timezone=True),
    server_default=func.now(),
)
    file_hash: Mapped[str] = mapped_column(String(64), unique=True)
    rows_total: Mapped[int] = mapped_column(default=0)
    rows_accepted: Mapped[int] = mapped_column(default=0)
    rows_rejected: Mapped[int] = mapped_column(default=0)
    status: Mapped[str] = mapped_column(String(20), default="PROCESSING")


class ImportRowError(Base):
    """One rejected row (or a header error with row_number 0). Source of the error report CSV."""

    __tablename__ = "import_errors"

    id: Mapped[int] = mapped_column(primary_key=True)
    batch_id: Mapped[int] = mapped_column(ForeignKey("import_batches.id"), index=True)
    row_number: Mapped[int]
    column_name: Mapped[str] = mapped_column(String(50))
    message: Mapped[str] = mapped_column(Text)


class Transaction(Base):
    __tablename__ = "transactions"
    __table_args__ = (
        CheckConstraint("quantity <> 0", name="ck_txn_quantity_nonzero"),
        CheckConstraint("unit_price_paise >= 0", name="ck_txn_price_nonneg"),
        CheckConstraint("discount_paise >= 0", name="ck_txn_discount_nonneg"),
        CheckConstraint("payment_mode IN ('CASH','UPI','CARD')", name="ck_txn_payment_mode"),
        CheckConstraint("is_return = (quantity < 0)", name="ck_txn_return_flag"),
        Index("ix_txn_sold_at", "sold_at"),
        Index("ix_txn_store_sold_at", "store_id", "sold_at"),
        Index("ix_txn_sku", "sku"),
        Index("ix_txn_original", "original_transaction_id"),
        Index("ix_txn_batch", "batch_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    transaction_id: Mapped[str] = mapped_column(String(50), unique=True)
    batch_id: Mapped[int] = mapped_column(ForeignKey("import_batches.id"))
    store_id: Mapped[int] = mapped_column(ForeignKey("stores.id"))
    sold_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    sku: Mapped[str] = mapped_column(ForeignKey("products.sku"))
    product_name: Mapped[str] = mapped_column(String(200))
    quantity: Mapped[int]
    unit_price_paise: Mapped[int] = mapped_column(BigInteger)
    discount_paise: Mapped[int] = mapped_column(BigInteger)
    line_total_paise: Mapped[int] = mapped_column(BigInteger)
    payment_mode: Mapped[str] = mapped_column(String(10))
    original_transaction_id: Mapped[str | None] = mapped_column(
        ForeignKey("transactions.transaction_id"), nullable=True
    )
    is_return: Mapped[bool] = mapped_column(Boolean)