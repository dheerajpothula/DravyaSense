/**
 * PCA Analysis API client
 * All requests go to /api/pca, proxied to FastAPI by Vite.
 */

import { handleResponse, ApiError } from './datasets'

export { ApiError }

// ── Types ────────────────────────────────────────────────────────

export type InputType = 'raw_dataset' | 'processed_dataset'

export interface PcaRunRequest {
  input_type:      InputType
  input_id:        string
  n_components:    number
  feature_columns?: string[] | null   // null = use all sensor columns
  experiment_name?: string | null
}

export interface PcaResult {
  experiment_id:          string | null   // null for unsaved /run
  input_type:             InputType
  input_id:               string
  source_filename:        string
  preprocessing_summary:  string | null
  experiment_name:        string | null

  // Feature matrix description
  n_samples:       number
  n_features:      number
  n_components:    number
  feature_columns: string[]

  // Metadata (never in feature matrix)
  sample_ids:      string[]
  category_labels: string[]     // empty list when no category column
  category_column: string | null

  // Variance
  explained_variance_ratio:  number[]
  cumulative_variance_ratio: number[]

  // Numerical results
  scores:   number[][]    // [n_samples][n_components]
  loadings: number[][]    // [n_components][n_features]

  // Reproducibility + diagnostics
  sklearn_version: string
  warnings:         string[]
  created_at:       string | null
}

export interface PcaExperimentSummary {
  id:                      string
  experiment_name:         string | null
  input_type:              string
  input_id:                string
  source_filename:         string
  preprocessing_summary:   string | null
  n_samples:               number
  n_features:               number
  n_components:             number
  explained_variance_ratio: string   // JSON list
  sklearn_version:          string
  created_at:               string
}

export interface DeletePcaResponse {
  deleted_id: string
  message:    string
}

// ── Endpoints ─────────────────────────────────────────────────────

export async function runPca(req: PcaRunRequest): Promise<PcaResult> {
  const res = await fetch('/api/pca/run', {
    method:  'POST',
    headers: { 'Content-Type': 'application/json' },
    body:    JSON.stringify(req),
  })
  return handleResponse<PcaResult>(res)
}

export async function savePca(req: PcaRunRequest): Promise<PcaResult> {
  const res = await fetch('/api/pca/save', {
    method:  'POST',
    headers: { 'Content-Type': 'application/json' },
    body:    JSON.stringify(req),
  })
  return handleResponse<PcaResult>(res)
}

export async function listPcaExperiments(
  sourceId?: string,
  inputType?: string,
): Promise<PcaExperimentSummary[]> {
  const params = new URLSearchParams()
  if (sourceId)  params.set('source_id', sourceId)
  if (inputType) params.set('input_type', inputType)
  const qs = params.toString()
  const res = await fetch(`/api/pca/experiments${qs ? '?' + qs : ''}`)
  return handleResponse<PcaExperimentSummary[]>(res)
}

export async function getPcaExperiment(id: string): Promise<PcaResult> {
  const res = await fetch(`/api/pca/experiments/${id}`)
  return handleResponse<PcaResult>(res)
}

export async function deletePcaExperiment(id: string): Promise<DeletePcaResponse> {
  const res = await fetch(`/api/pca/experiments/${id}`, { method: 'DELETE' })
  return handleResponse<DeletePcaResponse>(res)
}
