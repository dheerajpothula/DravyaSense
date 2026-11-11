/**
 * Preprocessing Studio API client
 * All requests go to /api/preprocessing, proxied to FastAPI by Vite.
 */

import { ApiError, handleResponse } from './datasets'

// ── Re-export error helper so callers can import from one place ───
export { ApiError }

// ── Configuration types ───────────────────────────────────────────

export type ImputationStrategy = 'mean' | 'median' | 'none'
export type ScalingMethod      = 'standard' | 'minmax' | 'robust' | 'none'
export type OutlierAction      = 'keep' | 'clip' | 'remove'

export interface PreprocessingConfig {
  selected_features:   string[]
  imputation_strategy: ImputationStrategy
  scaling_method:      ScalingMethod
  outlier_action:      OutlierAction
  iqr_multiplier:      number
}

// ── Preview ───────────────────────────────────────────────────────

export interface ColumnStatsBeforeAfter {
  column:         string
  before_mean:    number | null
  before_std:     number | null
  before_min:     number | null
  before_max:     number | null
  before_missing: number
  after_mean:     number | null
  after_std:      number | null
  after_min:      number | null
  after_max:      number | null
  after_missing:  number
}

export interface PreviewResponse {
  dataset_id:               string
  source_filename:          string
  row_count_before:         number
  row_count_after:          number
  columns:                  string[]
  selected_features:        string[]
  sample_id_column:         string | null
  category_columns:         string[]
  preview_rows:             (string | number | null)[][]
  transformations_applied:  string[]
  warnings:                 string[]
  column_stats:             ColumnStatsBeforeAfter[]
  processed_column_units:   Record<string, string>  // unit after transformation
}

// ── Processed dataset ─────────────────────────────────────────────

export interface ProcessedDatasetSummary {
  id:                   string
  source_dataset_id:    string
  source_filename:      string
  row_count:            number
  sensor_column_count:  number
  selected_features:    string   // JSON array — parse with JSON.parse()
  sklearn_version:      string
  created_at:           string
  scaler_type:          string | null   // derived from pipeline_config
}

export interface ProcessedDatasetDetail extends ProcessedDatasetSummary {
  processed_filename:      string
  file_size_bytes:         number
  column_count:            number
  missing_value_count:     number
  pipeline_config:         string   // JSON object
  transformations_applied: string   // JSON array
  column_units:            string | null  // JSON object
}

export interface ProcessedDatasetPreview {
  processed_id: string
  total_rows:   number
  page:         number
  page_size:    number
  columns:      string[]
  rows:         (string | number | null)[][]
}

export interface DeleteProcessedResponse {
  deleted_id: string
  message:    string
}

// ── Endpoints ─────────────────────────────────────────────────────

export async function previewPreprocessing(
  dataset_id: string,
  config: PreprocessingConfig,
): Promise<PreviewResponse> {
  const res = await fetch('/api/preprocessing/preview', {
    method:  'POST',
    headers: { 'Content-Type': 'application/json' },
    body:    JSON.stringify({ dataset_id, config }),
  })
  return handleResponse<PreviewResponse>(res)
}

export async function applyPreprocessing(
  dataset_id: string,
  config: PreprocessingConfig,
): Promise<ProcessedDatasetDetail> {
  const res = await fetch('/api/preprocessing/apply', {
    method:  'POST',
    headers: { 'Content-Type': 'application/json' },
    body:    JSON.stringify({ dataset_id, config }),
  })
  return handleResponse<ProcessedDatasetDetail>(res)
}

export async function listProcessedDatasets(
  source_dataset_id: string,
): Promise<ProcessedDatasetSummary[]> {
  const res = await fetch(`/api/preprocessing/dataset/${source_dataset_id}`)
  return handleResponse<ProcessedDatasetSummary[]>(res)
}

export async function getProcessedDetail(
  processed_id: string,
): Promise<ProcessedDatasetDetail> {
  const res = await fetch(`/api/preprocessing/${processed_id}`)
  return handleResponse<ProcessedDatasetDetail>(res)
}

export async function getProcessedPreview(
  processed_id: string,
  page = 1,
  pageSize = 20,
): Promise<ProcessedDatasetPreview> {
  const res = await fetch(
    `/api/preprocessing/${processed_id}/preview?page=${page}&page_size=${pageSize}`,
  )
  return handleResponse<ProcessedDatasetPreview>(res)
}

export async function deleteProcessed(
  processed_id: string,
): Promise<DeleteProcessedResponse> {
  const res = await fetch(`/api/preprocessing/${processed_id}`, { method: 'DELETE' })
  return handleResponse<DeleteProcessedResponse>(res)
}
