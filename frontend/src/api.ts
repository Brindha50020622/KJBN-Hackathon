export const API_BASE = (
  (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? "http://localhost:8000"
).replace(/\/$/, "");

export interface Batch {
  id: number;
  filename: string;
  uploaded_at: string;
  file_hash: string;
  rows_total: number;
  rows_accepted: number;
  rows_rejected: number;
  status: "PROCESSING" | "COMPLETED" | "REJECTED" | "FAILED";
  error_report_url: string | null;
}

export interface Page<T> {
  items: T[];
  total: number;
  limit: number;
  offset: number;
}

export interface Transaction {
  transaction_id: string;
  batch_id: number;
  store_code: string;
  sold_at: string;
  sold_at_ist: string;
  sku: string;
  product_name: string;
  quantity: number;
  unit_price_paise: number;
  discount_paise: number;
  line_total_paise: number;
  payment_mode: string;
  original_transaction_id: string | null;
  is_return: boolean;
}

export interface DayRevenue {
  day: string;
  revenue_paise: number;
}

export interface StoreRevenue {
  store_code: string;
  store_name: string;
  revenue_paise: number;
  transactions: number;
}

export interface ProductNet {
  sku: string;
  name: string;
  net_quantity: number;
  revenue_paise: number;
}

export interface StoreReturnRate {
  store_code: string;
  store_name: string;
  sold_quantity: number;
  returned_quantity: number;
  return_rate_percent: number;
}

export interface PaymentShare {
  payment_mode: string;
  revenue_paise: number;
  transactions: number;
}

export interface Dashboard {
  date_from: string | null;
  date_to: string | null;
  total_revenue_paise: number;
  total_transactions: number;
  revenue_by_day: DayRevenue[];
  revenue_by_store: StoreRevenue[];
  top_products: ProductNet[];
  return_rate_by_store: StoreReturnRate[];
  payment_split: PaymentShare[];
}

export class ApiError extends Error {
  status: number;
  code: string;
  requestId?: string;
  details?: unknown;

  constructor(status: number, code: string, message: string, requestId?: string, details?: unknown) {
    super(message);
    this.status = status;
    this.code = code;
    this.requestId = requestId;
    this.details = details;
  }
}

interface ErrorBody {
  error?: { code?: string; message?: string; request_id?: string; details?: unknown };
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE}${path}`, init);
  } catch {
    throw new ApiError(
      0,
      "NETWORK_ERROR",
      "Cannot reach the server. It may be starting up, so wait a minute and try again.",
    );
  }
  if (!response.ok) {
    let body: ErrorBody = {};
    try {
      body = (await response.json()) as ErrorBody;
    } catch {
      // response was not JSON
    }
    const err = body.error;
    throw new ApiError(
      response.status,
      err?.code ?? "HTTP_ERROR",
      err?.message ?? `Request failed (${response.status})`,
      err?.request_id,
      err?.details,
    );
  }
  return (await response.json()) as T;
}

type Params = Record<string, string | number | boolean | undefined>;

function query(params: Params): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === "" || value === false) continue;
    search.set(key, String(value));
  }
  const text = search.toString();
  return text ? `?${text}` : "";
}

export function uploadBatch(file: File): Promise<Batch> {
  const form = new FormData();
  form.append("file", file);
  return request<Batch>("/api/v1/batches", { method: "POST", body: form });
}

export const getBatch = (id: number) => request<Batch>(`/api/v1/batches/${id}`);

export const listBatches = (limit: number, offset: number) =>
  request<Page<Batch>>(`/api/v1/batches${query({ limit, offset })}`);

export const listTransactions = (params: Params) =>
  request<Page<Transaction>>(`/api/v1/transactions${query(params)}`);

export const getDashboard = (dateFrom?: string, dateTo?: string) =>
  request<Dashboard>(`/api/v1/dashboard${query({ date_from: dateFrom, date_to: dateTo })}`);