import { useState } from "react";
import {
  Bar, BarChart, CartesianGrid, Cell, Legend, Line, LineChart,
  Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";

import { getDashboard } from "../api";
import { ErrorBox, Loading } from "../components";
import { fillMissingDays, formatRupees, isRangeValid } from "../format";
import { useAsync } from "../useAsync";

const PAYMENT_COLORS: Record<string, string> = { CASH: "#16a34a", UPI: "#2563eb", CARD: "#f59e0b" };
const rupeeTip = (value: unknown) => formatRupees(Math.round(Number(value) * 100));
const axisRupees = (value: number) => `₹${new Intl.NumberFormat("en-IN").format(value)}`;
const shorten = (text: string) => (text.length > 18 ? `${text.slice(0, 17)}…` : text);

export default function DashboardPage() {
  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");
  const valid = isRangeValid(from, to);
  const { data, error, loading, reload } = useAsync(
    () => (valid ? getDashboard(from, to) : Promise.resolve(null)),
    [from, to],
  );

  const days = data ? fillMissingDays(data.revenue_by_day).map((d) => ({ day: d.day, revenue: d.revenue_paise / 100 })) : [];
  const stores = data ? data.revenue_by_store.map((s) => ({ name: s.store_code, revenue: s.revenue_paise / 100 })) : [];
  const products = data ? data.top_products.map((p) => ({ label: shorten(`${p.sku} ${p.name}`), quantity: p.net_quantity })) : [];
  const split = data
    ? data.payment_split.filter((p) => p.revenue_paise > 0).map((p) => ({ name: p.payment_mode, value: p.revenue_paise / 100 }))
    : [];
  const rates = new Map((data?.return_rate_by_store ?? []).map((r) => [r.store_code, r]));

  return (
    <>
      <h2>Dashboard</h2>
      <div className="card filters">
        <label>
          From
          <input type="date" value={from} max={to || undefined} onChange={(e) => setFrom(e.target.value)} />
        </label>
        <label>
          To
          <input type="date" value={to} min={from || undefined} onChange={(e) => setTo(e.target.value)} />
        </label>
        <button className="secondary" disabled={!from && !to} onClick={() => { setFrom(""); setTo(""); }}>
          Clear dates
        </button>
        <span className="muted">Dates are IST days. Leave empty for all data.</span>
      </div>

      {!valid && <div className="error" role="alert">"From" must not be after "To".</div>}
      {error && <ErrorBox error={error} onRetry={reload} />}
      {loading && !data && <Loading />}

      {data && valid && (
        <>
          <dl className="stats">
            <div><dt>Net revenue</dt><dd>{formatRupees(data.total_revenue_paise)}</dd></div>
            <div><dt>Transactions</dt><dd>{data.total_transactions}</dd></div>
          </dl>

          {data.total_transactions === 0 ? (
            <p className="card muted">No sales in this date range.</p>
          ) : (
            <div className="grid">
              <section className="card">
                <h3>Revenue by day</h3>
                <ResponsiveContainer width="100%" height={280}>
                  <LineChart data={days}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="day" tickFormatter={(d: string) => d.slice(5)} />
                    <YAxis tickFormatter={axisRupees} width={80} />
                    <Tooltip formatter={rupeeTip} />
                    <Line type="monotone" dataKey="revenue" stroke="#2563eb" dot={days.length < 31} />
                  </LineChart>
                </ResponsiveContainer>
              </section>

              <section className="card">
                <h3>Revenue by store</h3>
                <ResponsiveContainer width="100%" height={280}>
                  <BarChart data={stores}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="name" />
                    <YAxis tickFormatter={axisRupees} width={80} />
                    <Tooltip formatter={rupeeTip} />
                    <Bar dataKey="revenue" fill="#2563eb" />
                  </BarChart>
                </ResponsiveContainer>
              </section>

              <section className="card">
                <h3>Top 10 products by net quantity</h3>
                <ResponsiveContainer width="100%" height={360}>
                  <BarChart data={products} layout="vertical" margin={{ left: 10 }}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis type="number" />
                    <YAxis type="category" dataKey="label" width={130} />
                    <Tooltip />
                    <Bar dataKey="quantity" fill="#16a34a" />
                  </BarChart>
                </ResponsiveContainer>
              </section>

              <section className="card">
                <h3>Payment mode split (revenue)</h3>
                {split.length === 0 ? (
                  <p className="muted">No positive revenue in this range.</p>
                ) : (
                  <ResponsiveContainer width="100%" height={280}>
                    <PieChart>
                      <Pie data={split} dataKey="value" nameKey="name" outerRadius={90} label={(e: { name: string }) => e.name}>
                        {split.map((s) => (
                          <Cell key={s.name} fill={PAYMENT_COLORS[s.name] ?? "#64748b"} />
                        ))}
                      </Pie>
                      <Tooltip formatter={rupeeTip} />
                      <Legend />
                    </PieChart>
                  </ResponsiveContainer>
                )}
              </section>
            </div>
          )}

          <section className="card table-wrap" style={{ marginTop: 16 }}>
            <h3>Stores</h3>
            <table>
              <thead>
                <tr>
                  <th>Store</th><th className="num">Net revenue</th><th className="num">Transactions</th>
                  <th className="num">Units sold</th><th className="num">Units returned</th><th className="num">Return rate</th>
                </tr>
              </thead>
              <tbody>
                {data.revenue_by_store.map((s) => {
                  const r = rates.get(s.store_code);
                  return (
                    <tr key={s.store_code}>
                      <td>{s.store_code} · {s.store_name}</td>
                      <td className="num">{formatRupees(s.revenue_paise)}</td>
                      <td className="num">{s.transactions}</td>
                      <td className="num">{r?.sold_quantity ?? 0}</td>
                      <td className="num">{r?.returned_quantity ?? 0}</td>
                      <td className="num">{(r?.return_rate_percent ?? 0).toFixed(2)}%</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </section>
        </>
      )}
    </>
  );
}