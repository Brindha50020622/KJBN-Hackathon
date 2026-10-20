from app import service
from tests.helpers import csv_bytes, line

CLOCK = {"X-Test-Clock": "2026-10-18T12:00:00+05:30"}


def _upload(client, content):
    return client.post(
        "/api/v1/batches", files={"file": ("a.csv", content, "text/csv")}, headers=CLOCK
    )


def test_failed_import_is_marked_failed_and_can_be_retried(client, monkeypatch):
    content = csv_bytes(line("T-1"))
    real_run_import = service._run_import

    def boom(*_args):
        raise RuntimeError("database went away")

    monkeypatch.setattr(service, "_run_import", boom)
    first = _upload(client, content)
    assert first.status_code == 202
    assert client.get(f"/api/v1/batches/{first.json()['id']}").json()["status"] == "FAILED"

    monkeypatch.setattr(service, "_run_import", real_run_import)
    second = _upload(client, content)
    assert second.status_code == 202
    assert second.json()["id"] == first.json()["id"]
    body = client.get(f"/api/v1/batches/{second.json()['id']}").json()
    assert (body["status"], body["rows_accepted"]) == ("COMPLETED", 1)
