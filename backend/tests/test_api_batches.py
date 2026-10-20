import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.config import settings
from app.db import SessionLocal
from app.main import app
from app.models import ImportBatch, Product, ProductAlias, Transaction
from tests.helpers import HEADER, csv_bytes, line

SAMPLE = Path(__file__).resolve().parents[2] / "data" / "sample.csv"
CLOCK = {"X-Test-Clock": "2026-10-18T12:00:00+05:30"}


def upload(client, content, name="sales.csv", headers=CLOCK):
    return client.post(
        "/api/v1/batches", files={"file": (name, content, "text/csv")}, headers=headers
    )


def count(model):
    with SessionLocal() as session:
        return session.scalar(select(func.count()).select_from(model))


def batch(client, response):
    return client.get(f"/api/v1/batches/{response.json()['id']}").json()


def counts(body):
    return body["rows_accepted"], body["rows_rejected"]


# ---- happy path and idempotency ----


def test_upload_sample_file(client):
    response = upload(client, SAMPLE.read_bytes(), "sample.csv")
    assert response.status_code == 202
    body = batch(client, response)
    assert (body["status"], body["rows_total"], counts(body)) == ("COMPLETED", 12, (12, 0))
    assert body["error_report_url"] is None
    assert count(Transaction) == 12


def test_same_file_twice_is_a_duplicate_and_changes_nothing(client):
    upload(client, SAMPLE.read_bytes(), "sample.csv")
    again = upload(client, SAMPLE.read_bytes(), "renamed.csv")
    assert again.status_code == 409
    error = again.json()["error"]
    assert error["code"] == "DUPLICATE_FILE"
    assert error["details"]["batch_id"] == 1
    assert count(Transaction) == 12
    assert count(ImportBatch) == 1


def test_other_file_with_seen_ids_accepts_new_rows_and_rejects_repeats(client):
    upload(client, csv_bytes(line("T-1"), line("T-2")))
    body = batch(client, upload(client, csv_bytes(line("T-2"), line("T-3")), "b.csv"))
    assert counts(body) == (1, 1)
    assert "already imported" in client.get(body["error_report_url"]).text
    assert count(Transaction) == 3


def test_same_rows_in_other_order_are_all_rejected(client):
    upload(client, csv_bytes(line("T-1"), line("T-2")))
    response = upload(client, csv_bytes(line("T-2"), line("T-1")), "other.csv")
    assert response.status_code == 202
    assert counts(batch(client, response)) == (0, 2)


# ---- validation ----


def test_missing_column_rejects_whole_file(client):
    bad_header = HEADER.replace("unit_price,", "")
    body = batch(client, upload(client, csv_bytes(line("T-1"), header=bad_header)))
    assert body["status"] == "REJECTED"
    assert "unit_price" in client.get(body["error_report_url"]).text
    assert count(Transaction) == 0


def test_error_report_lists_row_column_and_reason(client):
    body = batch(client, upload(client, csv_bytes(line("T-1"), line("T-2", qty=0), line("T-3"))))
    assert counts(body) == (2, 1)
    report = client.get(body["error_report_url"])
    assert report.headers["content-type"].startswith("text/csv")
    assert "attachment" in report.headers["content-disposition"]
    assert report.text.splitlines() == ["row_number,column,message", "3,quantity,must not be zero"]


@pytest.mark.parametrize("options", [{"bom": True}, {"eol": "\r\n"}])
def test_bom_and_crlf_files_are_imported(client, options):
    body = batch(client, upload(client, csv_bytes(line("T-1"), line("T-2"), **options)))
    assert counts(body) == (2, 0)


def test_row_in_the_future_uses_the_test_clock(client):
    content = csv_bytes(
        line("T-1", at="2026-10-18 11:59:59"),
        line("T-2", at="2026-10-18 12:00:01"),
    )
    assert counts(batch(client, upload(client, content))) == (1, 1)


def test_return_before_original_in_same_file_is_accepted(client):
    rows = [line("R-1", qty=-1, orig="T-1", at="2026-10-11 16:00:00"), line("T-1", qty=3)]
    assert counts(batch(client, upload(client, csv_bytes(*rows)))) == (2, 0)


def test_return_over_original_quantity_across_two_files(client):
    first = [line("T-1", qty=3), line("R-1", qty=-2, orig="T-1", at="2026-10-11 16:00:00")]
    upload(client, csv_bytes(*first))
    second = [line("R-2", qty=-2, orig="T-1", at="2026-10-11 17:00:00")]
    body = batch(client, upload(client, csv_bytes(*second), "b.csv"))
    assert counts(body) == (0, 1)
    assert "more than the original" in client.get(body["error_report_url"]).text


def test_first_product_name_wins_and_alias_is_saved(client):
    other_name = "T-2,ST03,2026-10-11 14:32:10,SKU-114,Rice 5kg,1,540.00,0.00,UPI,"
    upload(client, csv_bytes(line("T-1"), other_name))
    with SessionLocal() as session:
        assert session.scalar(select(Product.name)) == "Basmati Rice 5kg"
        assert list(session.scalars(select(ProductAlias.alias))) == ["Rice 5kg"]


def test_twenty_thousand_rows_are_imported_in_chunks(client):
    rows = [
        line(f"B-{i:06d}", store=("ST01", "ST03")[i % 2], at=f"2026-09-{1 + i % 28:02d} 10:00:00")
        for i in range(20000)
    ]
    body = batch(client, upload(client, csv_bytes(*rows)))
    assert (body["status"], counts(body)) == ("COMPLETED", (20000, 0))
    assert count(Transaction) == 20000


# ---- concurrency ----


def _in_parallel(files):
    barrier = threading.Barrier(len(files))

    def send(item):
        index, content = item
        barrier.wait()
        return upload(TestClient(app), content, f"file{index}.csv").status_code

    with ThreadPoolExecutor(len(files)) as pool:
        return list(pool.map(send, enumerate(files)))


def test_same_file_uploaded_at_the_same_time_only_one_wins(db):
    codes = _in_parallel([SAMPLE.read_bytes()] * 6)
    assert sorted(codes) == [202] + [409] * 5
    assert count(Transaction) == 12


def test_overlapping_files_at_the_same_time_never_fail(db):
    first = csv_bytes(*[line(f"T-{i}") for i in range(1, 6)])
    second = csv_bytes(*[line(f"T-{i}") for i in range(3, 9)])
    assert _in_parallel([first, second]) == [202, 202]
    assert count(Transaction) == 8
    with SessionLocal() as session:
        assert set(session.scalars(select(ImportBatch.status))) == {"COMPLETED"}


# ---- list, errors, health ----


def test_batches_list_is_paged_newest_first(client):
    for i in range(3):
        upload(client, csv_bytes(line(f"T-{i}")), f"{i}.csv")
    page = client.get("/api/v1/batches", params={"limit": 2, "offset": 0}).json()
    assert page["total"] == 3
    assert [b["id"] for b in page["items"]] == [3, 2]
    assert client.get("/api/v1/batches", params={"limit": 0}).status_code == 422


def test_unknown_batch_is_404_with_standard_error_shape(client):
    response = client.get("/api/v1/batches/999")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"
    assert response.json()["error"]["request_id"]
    assert client.get("/api/v1/batches/999/errors.csv").status_code == 404


@pytest.mark.parametrize("batch_id", ["abc", "0", "99999999999"])
def test_batch_id_must_be_a_positive_int32(client, batch_id):
    response = client.get(f"/api/v1/batches/{batch_id}")
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_missing_file_field_is_a_validation_error(client):
    response = client.post("/api/v1/batches", headers=CLOCK)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_bad_test_clock_header_is_rejected(client):
    response = upload(client, csv_bytes(line("T-1")), headers={"X-Test-Clock": "yesterday"})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "INVALID_REQUEST"


def test_file_over_size_limit_is_413(client, monkeypatch):
    monkeypatch.setattr(settings, "max_upload_mb", 0)
    response = upload(client, csv_bytes(line("T-1")))
    assert response.status_code == 413
    assert response.json()["error"]["code"] == "FILE_TOO_LARGE"
    assert count(ImportBatch) == 0


def test_unexpected_error_hides_details(db, monkeypatch):
    def boom(*_args):
        raise RuntimeError("secret detail")

    monkeypatch.setattr("app.api.register_upload", boom)
    response = upload(TestClient(app, raise_server_exceptions=False), csv_bytes(line("T-1")))
    assert response.status_code == 500
    assert response.json()["error"]["code"] == "INTERNAL_ERROR"
    assert "secret detail" not in response.text
    assert "Traceback" not in response.text


def test_health_and_request_id_echo(client):
    response = client.get("/health", headers={"X-Request-ID": "abc-123"})
    assert response.json() == {"status": "ok"}
    assert response.headers["x-request-id"] == "abc-123"
