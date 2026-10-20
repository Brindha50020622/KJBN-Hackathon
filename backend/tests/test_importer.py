from datetime import UTC, datetime

import pytest

from app.importer import file_hash, import_file, parse_csv, plan_products
from app.rules import HeaderError, TxnInfo
from tests.helpers import HEADER, csv_bytes, line

NOW = datetime(2026, 10, 18, 12, 0, 0, tzinfo=UTC)
STORES = {"ST01", "ST03"}


def run(lines, known=None, returned=None, **kwargs):
    return import_file(csv_bytes(*lines, **kwargs), STORES, NOW, known or {}, returned or {})


def ids(result):
    return [t.transaction_id for t in result.accepted]


def issue_pairs(result):
    return [(i.row_number, i.column) for i in result.issues]


# ---- file level ----


def test_utf8_bom_is_removed():
    assert run([line("T-1")], bom=True).accepted[0].transaction_id == "T-1"


def test_crlf_line_endings_are_read():
    result = run([line("T-1"), line("T-2")], eol="\r\n")
    assert ids(result) == ["T-1", "T-2"]


def test_blank_lines_are_skipped():
    assert run([line("T-1"), "", ""]).rows_total == 1


def test_missing_column_rejects_whole_file():
    with pytest.raises(HeaderError):
        run([line("T-1")], header=HEADER.replace("unit_price,", ""))


def test_empty_file_rejects_whole_file():
    with pytest.raises(HeaderError):
        parse_csv(b"")


def test_invalid_utf8_rejects_whole_file():
    with pytest.raises(HeaderError):
        parse_csv(b"\xff\xfe\x00bad")


def test_header_only_file_has_zero_rows():
    result = run([])
    assert (result.rows_total, result.accepted, result.issues) == (0, [], [])


def test_same_bytes_give_same_hash_and_other_bytes_differ():
    assert file_hash(b"abc") == file_hash(b"abc")
    assert file_hash(b"abc") != file_hash(b"abd")


def test_row_with_wrong_column_count_is_rejected_and_rest_imported():
    result = run([line("T-1"), "T-2,ST03,only,three", line("T-3")])
    assert ids(result) == ["T-1", "T-3"]
    assert issue_pairs(result) == [(3, "row")]


# ---- row level ----


def test_bad_row_is_rejected_with_row_number_and_rest_imported():
    result = run([line("T-1"), line("T-2", qty=0), line("T-3")])
    assert ids(result) == ["T-1", "T-3"]
    assert issue_pairs(result) == [(3, "quantity")]


def test_counts_add_up():
    result = run([line("T-1"), line("T-2", qty=0), line("T-3", store="ST99")])
    assert result.rows_total == len(result.accepted) + result.rows_rejected == 3


def test_one_row_with_two_errors_counts_as_one_rejected_row():
    result = run([line("T-1", qty=0, store="ST99")])
    assert len(result.issues) == 2
    assert result.rows_rejected == 1


def test_line_total_and_paise_are_computed():
    txn = run([line("T-1", qty=2, discount="40.00")]).accepted[0]
    assert (txn.unit_price_paise, txn.discount_paise, txn.line_total_paise) == (54000, 4000, 104000)
    assert txn.is_return is False


def test_sold_at_is_stored_as_utc():
    txn = run([line("T-1")]).accepted[0]
    assert txn.sold_at == datetime(2026, 10, 11, 9, 2, 10, tzinfo=UTC)


# ---- duplicates ----


def test_repeated_id_inside_file_first_one_wins():
    result = run([line("T-1"), line("T-1", qty=5)])
    assert [t.quantity for t in result.accepted] == [2]
    assert issue_pairs(result) == [(3, "transaction_id")]


def test_id_already_in_database_is_rejected_and_new_rows_accepted():
    known = {"T-1": TxnInfo("T-1", "ST03", "SKU-114", 2, NOW)}
    result = run([line("T-1"), line("T-2")], known=known)
    assert ids(result) == ["T-2"]
    assert issue_pairs(result) == [(2, "transaction_id")]


def test_rejected_row_does_not_use_up_its_transaction_id():
    result = run([line("T-1", qty=0), line("T-1")])
    assert ids(result) == ["T-1"]
    assert issue_pairs(result) == [(2, "quantity")]


# ---- returns ----


def test_return_before_original_in_same_file_is_accepted():
    lines = [line("R-1", qty=-1, orig="T-1", at="2026-10-11 16:00:00"), line("T-1", qty=3)]
    result = run(lines)
    assert ids(result) == ["T-1", "R-1"]  # sale is inserted first
    assert result.issues == []


def test_two_returns_in_same_file_cannot_exceed_original():
    lines = [
        line("T-1", qty=3),
        line("R-1", qty=-2, orig="T-1", at="2026-10-11 16:00:00"),
        line("R-2", qty=-2, orig="T-1", at="2026-10-11 17:00:00"),
    ]
    result = run(lines)
    assert ids(result) == ["T-1", "R-1"]
    assert issue_pairs(result) == [(4, "quantity")]


def test_return_exceeding_original_across_two_files():
    known = {"T-1": TxnInfo("T-1", "ST03", "SKU-114", 3, datetime(2026, 10, 11, tzinfo=UTC))}
    returned = {"T-1": 2}
    result = run([line("R-9", qty=-2, orig="T-1", at="2026-10-11 16:00:00")], known, returned)
    assert result.accepted == []
    assert issue_pairs(result) == [(2, "quantity")]


def test_return_up_to_exact_remaining_quantity_across_files_is_accepted():
    known = {"T-1": TxnInfo("T-1", "ST03", "SKU-114", 3, datetime(2026, 10, 11, tzinfo=UTC))}
    result = run([line("R-9", qty=-1, orig="T-1", at="2026-10-11 16:00:00")], known, {"T-1": 2})
    assert ids(result) == ["R-9"]


def test_return_with_unknown_original_is_rejected():
    result = run([line("R-1", qty=-1, orig="T-404")])
    assert issue_pairs(result) == [(2, "original_transaction_id")]


def test_return_of_a_return_in_database_is_rejected():
    known = {"R-1": TxnInfo("R-1", "ST03", "SKU-114", -1, datetime(2026, 10, 11, tzinfo=UTC))}
    result = run([line("R-2", qty=-1, orig="R-1", at="2026-10-11 16:00:00")], known)
    assert issue_pairs(result) == [(2, "original_transaction_id")]


def test_return_of_a_return_in_same_file_is_rejected():
    lines = [
        line("T-1", qty=3),
        line("R-1", qty=-1, orig="T-1", at="2026-10-11 16:00:00"),
        line("R-2", qty=-1, orig="R-1", at="2026-10-11 17:00:00"),
    ]
    result = run(lines)
    assert ids(result) == ["T-1", "R-1"]
    assert issue_pairs(result) == [(4, "original_transaction_id")]


# ---- products ----


def test_first_product_name_wins_and_others_become_aliases():
    class Txn:
        def __init__(self, sku, name):
            self.sku, self.product_name = sku, name

    accepted = [Txn("S1", "Rice 5kg"), Txn("S1", "Basmati Rice 5kg"), Txn("S1", "Rice 5kg")]
    new, aliases = plan_products({}, accepted)
    assert new == {"S1": "Rice 5kg"}
    assert aliases == {("S1", "Basmati Rice 5kg")}


def test_existing_product_name_is_kept():
    class Txn:
        sku, product_name = "S1", "Other name"

    new, aliases = plan_products({"S1": "Rice 5kg"}, [Txn()])
    assert new == {}
    assert aliases == {("S1", "Other name")}
