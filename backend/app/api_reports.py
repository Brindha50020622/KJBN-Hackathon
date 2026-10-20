from datetime import date
from typing import Annotated

from fastapi import APIRouter, Query

from app import repository as repo
from app.api import DbSession
from app.dashboard import complete_payment_split, ist_range_to_utc, return_rate_percent
from app.errors import InvalidRequestError
from app.schemas import (
    DashboardOut,
    DayRevenue,
    PaymentShare,
    ProductNet,
    StoreReturnRate,
    StoreRevenue,
    TransactionPage,
    to_transaction_out,
)

router = APIRouter(prefix="/api/v1", tags=["reports"])


def _bounds(date_from: date | None, date_to: date | None):
    try:
        return ist_range_to_utc(date_from, date_to)
    except ValueError as exc:
        raise InvalidRequestError(str(exc)) from exc


@router.get("/transactions", response_model=TransactionPage)
def list_transactions(
    session: DbSession,
    store: Annotated[str | None, Query(max_length=20)] = None,
    sku: Annotated[str | None, Query(max_length=50)] = None,
    q: Annotated[str | None, Query(max_length=100)] = None,
    date_from: date | None = None,
    date_to: date | None = None,
    returns_only: bool = False,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0, le=10_000_000)] = 0,
):
    start, end = _bounds(date_from, date_to)
    rows, total = repo.search_transactions(
        session,
        store=store,
        start=start,
        end=end,
        sku=sku,
        returns_only=returns_only,
        q=q,
        limit=limit,
        offset=offset,
    )
    return TransactionPage(
        items=[to_transaction_out(txn, code) for txn, code in rows],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/dashboard", response_model=DashboardOut)
def dashboard(session: DbSession, date_from: date | None = None, date_to: date | None = None):
    start, end = _bounds(date_from, date_to)
    stores = repo.store_totals(session, start, end)
    return DashboardOut(
        date_from=date_from,
        date_to=date_to,
        total_revenue_paise=sum(s.revenue_paise for s in stores),
        total_transactions=sum(s.transactions for s in stores),
        revenue_by_day=[
            DayRevenue(day=day, revenue_paise=paise)
            for day, paise in repo.revenue_by_day(session, start, end)
        ],
        revenue_by_store=[
            StoreRevenue(
                store_code=s.code,
                store_name=s.name,
                revenue_paise=s.revenue_paise,
                transactions=s.transactions,
            )
            for s in stores
        ],
        top_products=[
            ProductNet(sku=sku, name=name, net_quantity=net, revenue_paise=paise)
            for sku, name, net, paise in repo.top_products(session, start, end)
        ],
        return_rate_by_store=[
            StoreReturnRate(
                store_code=s.code,
                store_name=s.name,
                sold_quantity=s.sold_quantity,
                returned_quantity=s.returned_quantity,
                return_rate_percent=return_rate_percent(s.returned_quantity, s.sold_quantity),
            )
            for s in stores
        ],
        payment_split=[
            PaymentShare(payment_mode=mode, revenue_paise=paise, transactions=count)
            for mode, paise, count in complete_payment_split(
                repo.payment_totals(session, start, end)
            )
        ],
    )
