import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";

import { API_BASE, ApiError, type Batch, getBatch, uploadBatch } from "../api";
import { ErrorBox, StatusBadge } from "../components";

const sleep = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

export default function UploadPage() {
  const [file, setFile] = useState<File | null>(null);
  const [dragging, setDragging] = useState(false);
  const [busy, setBusy] = useState(false);
  const [batch, setBatch] = useState<Batch | null>(null);
  const [error, setError] = useState<Error | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const alive = useRef(true);

  useEffect(() => {
    alive.current = true;
    return () => {
      alive.current = false;
    };
  }, []);

  function pick(chosen: File | undefined) {
    if (!chosen || busy) return;
    if (!chosen.name.toLowerCase().endsWith(".csv")) {
      setError(new Error("Please choose a .csv file."));
      return;
    }
    setFile(chosen);
    setBatch(null);
    setError(null);
  }

  async function submit() {
    if (!file) return;
    setBusy(true);
    setError(null);
    setBatch(null);
    try {
      let current = await uploadBatch(file);
      setBatch(current);
      while (alive.current && current.status === "PROCESSING") {
        await sleep(1000);
        current = await getBatch(current.id);
        setBatch(current);
      }
    } catch (e) {
      setError(e as Error);
    } finally {
      if (alive.current) setBusy(false);
    }
  }

  const duplicate = error instanceof ApiError && error.code === "DUPLICATE_FILE";

  return (
    <>
      <h2>Upload sales file</h2>
      <div
        className={`dropzone${dragging ? " active" : ""}`}
        role="button"
        tabIndex={0}
        onClick={() => inputRef.current?.click()}
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === " ") inputRef.current?.click();
        }}
        onDragOver={(e) => {
          e.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDragging(false);
          pick(e.dataTransfer.files[0]);
        }}
      >
        {file ? (
          <>
            <strong>{file.name}</strong> <span className="muted">({(file.size / 1024).toFixed(1)} KB)</span>
          </>
        ) : (
          "Drag a CSV file here, or click to choose one"
        )}
        <input
          ref={inputRef}
          type="file"
          accept=".csv,text/csv"
          hidden
          onChange={(e) => {
            pick(e.target.files?.[0]);
            e.target.value = "";
          }}
        />
      </div>
      <button disabled={!file || busy} onClick={submit}>
        {busy ? "Importing…" : "Upload"}
      </button>

      {error && <ErrorBox error={error} />}
      {duplicate && (
        <p>
          Nothing was changed. <Link to="/batches">See batch history</Link>.
        </p>
      )}

      {batch && (
        <section className="card" style={{ marginTop: 16 }}>
          <h3>
            {batch.filename} <StatusBadge status={batch.status} />
          </h3>
          {batch.status === "PROCESSING" && (
            <p className="muted">Import is running. This page updates by itself.</p>
          )}
          {batch.status === "COMPLETED" && (
            <dl className="stats">
              <div><dt>Rows</dt><dd>{batch.rows_total}</dd></div>
              <div><dt>Accepted</dt><dd>{batch.rows_accepted}</dd></div>
              <div><dt>Rejected</dt><dd>{batch.rows_rejected}</dd></div>
            </dl>
          )}
          {batch.status === "REJECTED" && (
            <p>The whole file was rejected because of a missing or invalid header. See the error report.</p>
          )}
          {batch.status === "FAILED" && (
            <p>The import failed on the server and nothing was saved. Upload the same file again to retry.</p>
          )}
          {batch.error_report_url && (
            <a href={`${API_BASE}${batch.error_report_url}`}>Download error report (CSV)</a>
          )}
        </section>
      )}
    </>
  );
}