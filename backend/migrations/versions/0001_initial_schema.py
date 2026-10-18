"""initial schema"""

import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None


def upgrade() -> None:
    op.create_table(
        "stores",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("code", sa.String(20), nullable=False, unique=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("city", sa.String(100), nullable=False),
    )
    op.create_table(
        "products",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("sku", sa.String(50), nullable=False, unique=True),
        sa.Column("name", sa.String(200), nullable=False),
    )
    op.create_table(
        "product_aliases",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("product_id", sa.Integer, sa.ForeignKey("products.id"), nullable=False),
        sa.Column("alias", sa.String(200), nullable=False),
        sa.UniqueConstraint("product_id", "alias", name="uq_alias_per_product"),
    )
    op.create_table(
        "import_batches",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("filename", sa.String(255), nullable=False),
        sa.Column(
            "uploaded_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("file_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("rows_total", sa.Integer, nullable=False, server_default="0"),
        sa.Column("rows_accepted", sa.Integer, nullable=False, server_default="0"),
        sa.Column("rows_rejected", sa.Integer, nullable=False, server_default="0"),
        sa.Column("status", sa.String(20), nullable=False, server_default="PROCESSING"),
        sa.CheckConstraint(
            "status IN ('PROCESSING','COMPLETED','REJECTED','FAILED')", name="ck_batch_status"
        ),
    )
    op.create_table(
        "import_errors",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("batch_id", sa.Integer, sa.ForeignKey("import_batches.id"), nullable=False),
        sa.Column("row_number", sa.Integer, nullable=False),
        sa.Column("column_name", sa.String(50), nullable=False),
        sa.Column("message", sa.Text, nullable=False),
    )
    op.create_index("ix_import_errors_batch_id", "import_errors", ["batch_id"])
    op.create_table(
        "transactions",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("transaction_id", sa.String(50), nullable=False, unique=True),
        sa.Column("batch_id", sa.Integer, sa.ForeignKey("import_batches.id"), nullable=False),
        sa.Column("store_id", sa.Integer, sa.ForeignKey("stores.id"), nullable=False),
        sa.Column("sold_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("sku", sa.String(50), sa.ForeignKey("products.sku"), nullable=False),
        sa.Column("product_name", sa.String(200), nullable=False),
        sa.Column("quantity", sa.Integer, nullable=False),
        sa.Column("unit_price_paise", sa.BigInteger, nullable=False),
        sa.Column("discount_paise", sa.BigInteger, nullable=False),
        sa.Column("line_total_paise", sa.BigInteger, nullable=False),
        sa.Column("payment_mode", sa.String(10), nullable=False),
        sa.Column(
            "original_transaction_id",
            sa.String(50),
            sa.ForeignKey("transactions.transaction_id"),
            nullable=True,
        ),
        sa.Column("is_return", sa.Boolean, nullable=False),
        sa.CheckConstraint("quantity <> 0", name="ck_txn_quantity_nonzero"),
        sa.CheckConstraint("unit_price_paise >= 0", name="ck_txn_price_nonneg"),
        sa.CheckConstraint("discount_paise >= 0", name="ck_txn_discount_nonneg"),
        sa.CheckConstraint("payment_mode IN ('CASH','UPI','CARD')", name="ck_txn_payment_mode"),
        sa.CheckConstraint("is_return = (quantity < 0)", name="ck_txn_return_flag"),
    )
    op.create_index("ix_txn_sold_at", "transactions", ["sold_at"])
    op.create_index("ix_txn_store_sold_at", "transactions", ["store_id", "sold_at"])
    op.create_index("ix_txn_sku", "transactions", ["sku"])
    op.create_index("ix_txn_original", "transactions", ["original_transaction_id"])
    op.create_index("ix_txn_batch", "transactions", ["batch_id"])


def downgrade() -> None:
    for table in (
        "transactions",
        "import_errors",
        "import_batches",
        "product_aliases",
        "products",
        "stores",
    ):
        op.drop_table(table)