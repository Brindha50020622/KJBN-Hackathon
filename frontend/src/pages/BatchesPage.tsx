import { useEffect, useState } from "react";

import { API_BASE, listBatches } from "../api";
import { ErrorBox, Loading, Pager, StatusBadge } from "../components";
import { formatIstDateTime } from "../format";
import { useAsync } from "../useAsync";

const PAGE_SIZE = 20;

export default function BatchesPage() {
  const [offset, setOffset] = useState(0);
  const { data, error, loading, reload } = useAsync(() => listBatches(PAGE_SIZE, offset), [offset]);

  const running = data?.items.some((b) => b.status === "PROCESSING") ?? false;
  useEffect(() => {
    if (!running) return;
    const timer = setInterval(reload, 3000);
    return () => clearInterval(timer);
  }, [running, reload]);

  return (
    <>
      <h2>Batch history</h2>
      {error && <ErrorBox error={error} onRetry={reload} />}
      {loading && !data && <Loading />}
      {data && data.items.length === 0 && <p className="muted">No files uploaded yet.</p>}
      {data && data.items.length > 0 && (
        <div className="card table-wrap">
          <table>
            <thead>
              <tr>
                <th>ID</th><th>File</th><th>Uploaded (IST)</th><th>Status</th>
                <th className="num">Rows</th><th className="num">Accepted</th><th className="num">Rejected</th>
                <th>Error report</th>
              </tr>
            </thead>
            <tbody>
              {data.items.map((b) => (
                <tr key={b.id}>
                  <td>{b.id}</td>
                  <td>{b.filename}</td>
                  <td>{formatIstDateTime(b.uploaded_at)}</td>
                  <td><StatusBadge status={b.status} /></td>
                  <td className="num">{b.rows_total}</td>
                  <td className="num">{b.rows_accepted}</td>
                  <td className="num">{b.rows_rejected}</td>
                  <td>
                    {b.error_report_url ? <a href={`${API_BASE}${b.error_report_url}`}>Download CSV</a> : "–"}
                  </td>
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