from app.rules import REQUIRED_COLUMNS

HEADER = ",".join(REQUIRED_COLUMNS)


def line(
    tid,
    qty=2,
    store="ST03",
    sku="SKU-114",
    at="2026-10-11 14:32:10",
    orig="",
    discount="0.00",
):
    return f"{tid},{store},{at},{sku},Basmati Rice 5kg,{qty},540.00,{discount},UPI,{orig}"


def csv_bytes(*lines, eol="\n", bom=False, header=HEADER):
    body = eol.join([header, *lines]) + eol
    return (b"\xef\xbb\xbf" if bom else b"") + body.encode("utf-8")
