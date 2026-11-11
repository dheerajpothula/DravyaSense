/**
 * t-SNE Analysis API client
 * All requests go to /api/tsne, proxied to FastAPI by Vite.
 */

import { handleResponse, ApiError } from './datasets'

export { ApiError }

// ── Types ────────────────────────────────────────────────────────

export type InputType = 'raw_dataset' | 'processed_dataset'

export interface TsneRunRequest {
  input_type:         InputType
  input_id:           string
  n_components:       number             // 2 or 3
  perplexity:         number             // must be < n_samples
  learning_rate:      number | 'auto'
  early_exaggeration: number
  max_iter:           number
  random_state:       number
  metric:             string
  init:               'pca' | 'random'
  feature_columns?:   string[] | null    // null = use all sensor columns
  experiment_name?:   string | null
}

export interface TsneResult {
  experiment_id:         string | null   // null for unsaved /run
  input_type:            InputType
  input_id:              string
  source_filename:       string
  preprocessing_summary: string | null
  experiment_name:       string | null

  // Feature matrix description
  n_samples:       number
  n_features:      number
  n_components:    number   // 2 or 3
  feature_columns: string[]

  // Metadata (never in feature matrix)
  sample_ids:      string[]
  category_labels: string[]   // empty when no category column
  category_column: string | null

  // t-SNE hyperparameters (effective / resolved values)
  perplexity:          number
  learning_rate:       number   // resolved — never "auto"
  early_exaggeration:  number
  max_iter:            number
  random_state:        number
  metric:              string
  init:                string

  // Embedding coordinates — shape: n_samples × n_components
  embedding: number[][]

  // Reproducibility + diagnostics
  sklearn_version: string
  warnings:         string[]
  created_at:       string | null
}

export interface TsneExperimentSummary {
  id:                    string
  experiment_name:       string | null
  input_type:            string
  input_id:              string
  source_filename:       string
  preprocessing_summary: string | null
  n_samples:             number
  n_features:            number
  n_components:          number
  perplexity:            number
  learning_rate:         number
  early_exaggeration:    number
  max_iter:              number
  random_state:          number
  metric:                string
  init:                  string
  sklearn_version:       string
  created_at:            string
}

export interface DeleteTsneResponse {
  deleted_id: string
  message:    string
}

// ── Endpoints ─────────────────────────────────────────────────────

export async function runTsne(req: TsneRunRequest): Promise<TsneResult> {
  const res = await fetch('/api/tsne/run', {
    method:  'POST',
    headers: { 'Content-Type': 'application/json' },
    body:    JSON.stringify(req),
  })
  return handleResponse<TsneResult>(res)
}

export async function saveTsne(req: TsneRunRequest): Promise<TsneResult> {
  const res = await fetch('/api/tsne/save', {
    method:  'POST',
    headers: { 'Content-Type': 'application/json' },
    body:    JSON.stringify(req),
  })
  return handleResponse<TsneResult>(res)
}

export async function listTsneExperiments(
  sourceId?: string,
  inputType?: string,
): Promise<TsneExperimentSummary[]> {
  const params = new URLSearchParams()
  if (sourceId)  params.set('source_id', sourceId)
  if (inputType) params.set('input_type', inputType)
  const qs = params.toString()
  const res = await fetch(`/api/tsne/experiments${qs ? '?' + qs : ''}`)
  return handleResponse<TsneExperimentSummary[]>(res)
}

export async function getTsneExperiment(id: string): Promise<TsneResult> {
  const res = await fetch(`/api/tsne/experiments/${id}`)
  return handleResponse<TsneResult>(res)
}

export async function deleteTsneExperiment(id: string): Promise<DeleteTsneResponse> {
  const res = await fetch(`/api/tsne/experiments/${id}`, { method: 'DELETE' })
  return handleResponse<DeleteTsneResponse>(res)
}
