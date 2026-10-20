from sqlalchemy import func, select

from app.bootstrap import load_history
from app.db import SessionLocal
from app.models import ImportBatch, Transaction
from tests.helpers import csv_bytes, line


def test_history_is_loaded_only_once(db, tmp_path):
    path = tmp_path / "history.csv"
    path.write_bytes(csv_bytes(line("H-1"), line("H-2")))
    load_history(path)
    load_history(path)
    with SessionLocal() as session:
        assert session.scalar(select(func.count()).select_from(Transaction)) == 2
        assert session.scalar(select(func.count()).select_from(ImportBatch)) == 1


def test_missing_history_file_is_skipped(db, tmp_path):
    load_history(tmp_path / "nope.csv")
