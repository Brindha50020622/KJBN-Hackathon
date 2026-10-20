import { type FormEvent, useState } from "react";

import { getDashboard, listTransactions } from "../api";
import { ErrorBox, Loading, Pager } from "../components";
import { formatRupees, isRangeValid } from "../format";
import { useAsync } from "../useAsync";

interface Filters {
  store: string;
  sku: string;
  q: string;
  from: string;
  to: string;
  returnsOnly: boolean;
}

const EMPTY: Filters = { store: "", sku: "", q: "", from: "", to: "", returnsOnly: false };
const PAGE_SIZE = 25;

export default function TransactionsPage() {
  const [draft, setDraft] = useState<Filters>(EMPTY);
  const [applied, setApplied] = useState<Filters>(EMPTY);
  const [offset, setOffset] = useState(0);
  const valid = isRangeValid(draft.from, draft.to);

  const stores = useAsync(() => getDashboard(), []);
  const list = useAsync(
    () =>
      listTransactions({
        store: applied.store,
        sku: applied.sku.trim(),
        q: applied.q.trim(),
        date_from: applied.from,
        date_to: applied.to,
        returns_only: applied.returnsOnly,
        limit: PAGE_SIZE,
        offset,
      }),
    [applied, offset],
  );

  function set<K extends keyof Filters>(key: K, value: Filters[K]) {
    setDraft((d) => ({ ...d, [key]: value }));
  }

  function search(e: FormEvent) {
    e.preventDefault();
    if (!valid) return;
    setApplied(draft);
    setOffset(0);
  }

  function reset() {
    setDraft(EMPTY);
    setApplied(EMPTY);
    setOffset(0);
  }

  const { data, error, loading, reload } = list;

  return (
    <>
      <h2>Transactions</h2>
      <form className="card filters" onSubmit={search}>
        <label>
          Store
          <select value={draft.store} onChange={(e) => set("store", e.target.value)}>
            <option value="">All stores</option>
            {stores.data?.revenue_by_store.map((s) => (
              <option key={s.store_code} value={s.store_code}>{s.store_code} · {s.store_name}</option>
            ))}
          </select>
        </label>
        <label>
          SKU
          <input value={draft.sku} maxLength={50} onChange={(e) => set("sku", e.target.value)} />
        </label>
        <label>
          Search id or product
          <input value={draft.q} maxLength={100} onChange={(e) => set("q", e.target.value)} />
        </label>
        <label>
          From
          <input type="date" value={draft.from} max={draft.to || undefined} onChange={(e) => set("from", e.target.value)} />
        </label>
        <label>
          To
          <input type="date" value={draft.to} min={draft.from || undefined} onChange={(e) => set("to", e.target.value)} />
        </label>
        <label className="inline">
          <input type="checkbox" checked={draft.returnsOnly} onChange={(e) => set("returnsOnly", e.target.checked)} />
          Returns only
        </label>
        <button type="submit" disabled={!valid}>Search</button>
        <button type="button" className="secondary" onClick={reset}>Reset</button>
      </form>

      {error && <ErrorBox error={error} onRetry={reload} />}
      {loading && !data && <Loading />}
      {data && data.items.length === 0 && <p className="muted">No transactions match these filters.</p>}
      {data && data.items.length > 0 && (
        <div className="card table-wrap">
          <table>
            <thead>
              <tr>
                <th>Time (IST)</th><th>Transaction</th><th>Store</th><th>SKU</th><th>Product</th>
                <th className="num">Qty</th><th className="num">Unit price</th><th className="num">Discount</th>
                <th className="num">Line total</th><th>Payment</th><th>Original</th>
              </tr>
            </thead>
            <tbody>
              {data.items.map((t) => (
                <tr key={t.transaction_id} className={t.is_return ? "return" : undefined}>
                  <td>{t.sold_at_ist}</td>
                  <td>{t.transaction_id}</td>
                  <td>{t.store_code}</td>
                  <td>{t.sku}</td>
                  <td>{t.product_name}</td>
                  <td className="num">{t.quantity}</td>
                  <td className="num">{formatRupees(t.unit_price_paise)}</td>
                  <td className="num">{formatRupees(t.discount_paise)}</td>
                  <td className="num">{formatRupees(t.line_total_paise)}</td>
                  <td>{t.payment_mode}</td>
                  <td>{t.original_transaction_id ?? "–"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {data && <Pager total={data.total} limit={PAGE_SIZE} offset={offset} onChange={setOffset} />}
    </>
  );
}