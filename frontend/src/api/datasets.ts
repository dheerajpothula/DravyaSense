/**
 * Dataset API client
 * All requests go to /api/datasets, proxied to FastAPI by Vite.
 */

export interface ColumnInfo {
  name:           string
  detected_role:  ColumnRole
  dtype:          string
  missing_count:  number
  unique_count:   number
  sample_values:  (string | number | null)[]
}

export type ColumnRole = 'sensor' | 'sample_id' | 'category' | 'ignored'

export interface UploadAnalysis {
  dataset_id:          string
  filename:            string
  row_count:           number
  column_count:        number
  columns:             ColumnInfo[]
  missing_value_count: number
  warnings:            string[]
}

export interface DatasetSummary {
  id:                  string
  original_filename:   string
  file_size_bytes:     number
  row_count:           number
  column_count:        number
  sensor_column_count: number
  missing_value_count: number
  created_at:          string
}

export interface DatasetDetail extends DatasetSummary {
  stored_filename: string
  mime_type:       string
  column_roles:    string   // raw JSON — parse with JSON.parse()
  notes:           string | null
  updated_at:      string
}

export interface DatasetPreview {
  dataset_id: string
  total_rows: number
  page:       number
  page_size:  number
  columns:    string[]
  rows:       (string | number | null)[][]
}

export interface DeleteResponse {
  deleted_id: string
  message:    string
}

// ── API error helper ──────────────────────────────────────────────

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    message: string,
  ) {
    super(message)
    this.name = 'ApiError'
  }
}

async function handleResponse<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let detail = `HTTP ${res.status}`
    try {
      const body = await res.json()
      detail = typeof body.detail === 'string'
        ? body.detail
        : JSON.stringify(body.detail)
    } catch { /* ignore */ }
    throw new ApiError(res.status, detail)
  }
  return res.json() as Promise<T>
}

// ── Endpoints ─────────────────────────────────────────────────────

export async function uploadDataset(file: File): Promise<UploadAnalysis> {
  const form = new FormData()
  form.append('file', file)
  const res = await fetch('/api/datasets/upload', { method: 'POST', body: form })
  return handleResponse<UploadAnalysis>(res)
}

export async function listDatasets(): Promise<DatasetSummary[]> {
  const res = await fetch('/api/datasets')
  return handleResponse<DatasetSummary[]>(res)
}

export async function getDataset(id: string): Promise<DatasetDetail> {
  const res = await fetch(`/api/datasets/${id}`)
  return handleResponse<DatasetDetail>(res)
}

export async function confirmRoles(
  id: string,
  roles: Record<string, ColumnRole>,
): Promise<DatasetDetail> {
  const res = await fetch(`/api/datasets/${id}/roles`, {
    method:  'PUT',
    headers: { 'Content-Type': 'application/json' },
    body:    JSON.stringify({ column_roles: roles }),
  })
  return handleResponse<DatasetDetail>(res)
}

export async function getPreview(
  id: string,
  page = 1,
  pageSize = 20,
): Promise<DatasetPreview> {
  const res = await fetch(
    `/api/datasets/${id}/preview?page=${page}&page_size=${pageSize}`,
  )
  return handleResponse<DatasetPreview>(res)
}

export async function deleteDataset(id: string): Promise<DeleteResponse> {
  const res = await fetch(`/api/datasets/${id}`, { method: 'DELETE' })
  return handleResponse<DeleteResponse>(res)
}
