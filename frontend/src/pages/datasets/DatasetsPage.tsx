import { useCallback, useEffect, useState } from 'react'
import {
  type ColumnRole,
  type DatasetDetail,
  type DatasetPreview,
  type DatasetSummary,
  type UploadAnalysis,
  ApiError,
  confirmRoles,
  deleteDataset,
  getDataset,
  getPreview,
  listDatasets,
  uploadDataset,
} from '../../api/datasets'
import ColumnRoleEditor from '../../components/ColumnRoleEditor'
import DataPreviewTable from '../../components/DataPreviewTable'
import UploadZone from '../../components/UploadZone'

/* ─────────────────────────────────────────────────────────────────
   State machine:
     idle        — empty list or ready for upload
     uploading   — file being sent
     reviewing   — UploadAnalysis received, awaiting role confirmation
     confirming  — PUT /roles in flight
     confirmed   — roles saved, showing dataset detail
     error       — upload or network failure
───────────────────────────────────────────────────────────────── */
type Phase = 'idle' | 'uploading' | 'reviewing' | 'confirming' | 'confirmed' | 'error'

export default function DatasetsPage() {
  // ── Dataset list ─────────────────────────────────────────────
  const [datasets,    setDatasets]    = useState<DatasetSummary[]>([])
  const [listLoading, setListLoading] = useState(true)
  const [listError,   setListError]   = useState<string | null>(null)

  // ── Upload flow ──────────────────────────────────────────────
  const [phase,      setPhase]      = useState<Phase>('idle')
  const [analysis,   setAnalysis]   = useState<UploadAnalysis | null>(null)
  const [uploadErr,  setUploadErr]  = useState<string | null>(null)

  // ── Selected dataset detail + preview ────────────────────────
  const [selected,        setSelected]        = useState<DatasetDetail | null>(null)
  const [preview,         setPreview]         = useState<DatasetPreview | null>(null)
  const [previewPage,     setPreviewPage]     = useState(1)
  const [previewLoading,  setPreviewLoading]  = useState(false)

  // ── Delete confirmation ──────────────────────────────────────
  const [deleteTarget,  setDeleteTarget]  = useState<string | null>(null)
  const [deleting,      setDeleting]      = useState(false)

  // ── Load dataset list ────────────────────────────────────────
  const refreshList = useCallback(async () => {
    setListLoading(true)
    setListError(null)
    try {
      setDatasets(await listDatasets())
    } catch {
      setListError('Could not load datasets. Is the backend running?')
    } finally {
      setListLoading(false)
    }
  }, [])

  useEffect(() => { refreshList() }, [refreshList])

  // ── Handle file selection ────────────────────────────────────
  const handleFile = useCallback(async (file: File) => {
    setPhase('uploading')
    setUploadErr(null)
    setAnalysis(null)
    try {
      const result = await uploadDataset(file)
      setAnalysis(result)
      setPhase('reviewing')
      await refreshList()
    } catch (err) {
      const msg = err instanceof ApiError ? err.message : 'Upload failed. Please try again.'
      setUploadErr(msg)
      setPhase('error')
    }
  }, [refreshList])

  // ── Confirm roles ────────────────────────────────────────────
  const handleConfirmRoles = useCallback(async (roles: Record<string, ColumnRole>) => {
    if (!analysis) return
    setPhase('confirming')
    try {
      const detail = await confirmRoles(analysis.dataset_id, roles)
      setSelected(detail)
      setPhase('confirmed')
      await refreshList()
      await loadPreview(detail.id, 1)
    } catch (err) {
      const msg = err instanceof ApiError ? err.message : 'Could not save column roles.'
      setUploadErr(msg)
      setPhase('error')
    }
  }, [analysis, refreshList])

  // ── Load preview ─────────────────────────────────────────────
  const loadPreview = useCallback(async (id: string, page: number) => {
    setPreviewLoading(true)
    try {
      const p = await getPreview(id, page, 20)
      setPreview(p)
      setPreviewPage(page)
    } catch { /* preview is best-effort */ } finally {
      setPreviewLoading(false)
    }
  }, [])

  // ── Select existing dataset ──────────────────────────────────
  const handleSelect = useCallback(async (id: string) => {
    try {
      const detail = await getDataset(id)
      setSelected(detail)
      setAnalysis(null)
      setPhase('confirmed')
      await loadPreview(id, 1)
    } catch { /* ignore */ }
  }, [loadPreview])

  // ── Delete ───────────────────────────────────────────────────
  const handleDelete = useCallback(async () => {
    if (!deleteTarget) return
    setDeleting(true)
    try {
      await deleteDataset(deleteTarget)
      if (selected?.id === deleteTarget) {
        setSelected(null)
        setPreview(null)
        setPhase('idle')
      }
      setDeleteTarget(null)
      await refreshList()
    } catch { /* ignore */ } finally {
      setDeleting(false)
    }
  }, [deleteTarget, selected, refreshList])

  // ── Reset to upload another ──────────────────────────────────
  const resetUpload = () => {
    setPhase('idle')
    setAnalysis(null)
    setUploadErr(null)
  }

  /* ── Render ─────────────────────────────────────────────── */
  return (
    <div className="flex flex-col gap-8">

      {/* ── Page header ──────────────────────────────────────── */}
      <div className="pb-6 border-b border-surface-border">
        <p className="eyebrow mb-3">
          <span className="w-5 h-px bg-text-muted inline-block" />
          Module 01
        </p>
        <h1 className="font-serif text-display-sm text-text-primary mb-2 leading-tight">
          Dataset Management
        </h1>
        <p className="text-text-secondary text-sm leading-relaxed max-w-xl">
          Upload CSV or Excel files containing electronic-tongue sensor readings.
          Column roles are detected automatically and must be confirmed before analysis.
          Raw uploaded files are never modified.
        </p>
      </div>

      {/* ── Main layout — upload panel + dataset list ─────────── */}
      <div className="grid lg:grid-cols-5 gap-6">

        {/* Left — upload + review panel (3/5) */}
        <div className="lg:col-span-3 flex flex-col gap-4">

          {/* Upload zone */}
          {(phase === 'idle' || phase === 'error') && (
            <div className="border border-surface-border bg-brand-white">
              <div className="px-6 py-5 border-b border-surface-border">
                <h2 className="font-serif text-base text-text-primary">Upload Dataset</h2>
              </div>
              <div className="p-6">
                <UploadZone onFile={handleFile} />

                {uploadErr && (
                  <div className="mt-4 flex items-start gap-2 px-4 py-3
                                  bg-red-50 border border-red-200 rounded-sm">
                    <ErrorIcon className="w-4 h-4 text-red-500 shrink-0 mt-0.5" />
                    <div>
                      <p className="text-sm font-medium text-red-800 mb-0.5">Upload failed</p>
                      <p className="text-sm text-red-700">{uploadErr}</p>
                      <button
                        onClick={resetUpload}
                        className="mt-2 text-xs text-red-700 underline hover:no-underline"
                      >
                        Try again
                      </button>
                    </div>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Upload in progress */}
          {phase === 'uploading' && (
            <div className="border border-surface-border bg-brand-white p-8
                            flex flex-col items-center gap-4 text-center">
              <div className="w-10 h-10 border-2 border-surface-border border-t-forest-900
                              rounded-full animate-spin" />
              <p className="text-sm text-text-secondary">Uploading and analysing file…</p>
            </div>
          )}

          {/* Column role review */}
          {(phase === 'reviewing' || phase === 'confirming') && analysis && (
            <div className="border border-surface-border bg-brand-white">
              {/* Upload summary header */}
              <div className="px-6 py-4 border-b border-surface-border
                              flex items-center justify-between gap-4 flex-wrap">
                <div>
                  <h2 className="font-serif text-base text-text-primary">
                    {analysis.filename}
                  </h2>
                  <p className="text-xs text-text-muted mt-0.5">
                    {analysis.row_count} rows · {analysis.column_count} columns
                    {analysis.missing_value_count > 0
                      ? ` · ${analysis.missing_value_count} missing values`
                      : ''}
                  </p>
                </div>
                <button
                  onClick={resetUpload}
                  className="text-xs text-text-muted hover:text-text-primary
                             underline underline-offset-2 transition-colors duration-150"
                >
                  ← Upload different file
                </button>
              </div>

              {/* Warnings */}
              {analysis.warnings.length > 0 && (
                <div className="px-6 pt-4">
                  <div className="flex flex-col gap-2">
                    {analysis.warnings.map((w, i) => (
                      <div key={i} className="flex items-start gap-2 px-4 py-3
                                              bg-amber-50 border border-amber-200 rounded-sm">
                        <WarnIcon className="w-4 h-4 text-amber-600 shrink-0 mt-0.5" />
                        <p className="text-sm text-amber-800">{w}</p>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Role editor */}
              <ColumnRoleEditor
                columns={analysis.columns}
                onConfirm={handleConfirmRoles}
                confirming={phase === 'confirming'}
              />
            </div>
          )}

          {/* Confirmed — dataset detail + preview */}
          {phase === 'confirmed' && selected && (
            <DatasetDetailPanel
              dataset={selected}
              preview={preview}
              previewPage={previewPage}
              previewLoading={previewLoading}
              onPageChange={(p) => loadPreview(selected.id, p)}
              onUploadAnother={resetUpload}
              onDelete={() => setDeleteTarget(selected.id)}
            />
          )}
        </div>

        {/* Right — dataset list (2/5) */}
        <div className="lg:col-span-2">
          <div className="border border-surface-border bg-brand-white">
            <div className="px-5 py-4 border-b border-surface-border flex items-center justify-between">
              <h2 className="font-serif text-base text-text-primary">Uploaded Datasets</h2>
              {!listLoading && (
                <span className="text-xs text-text-muted font-mono">{datasets.length}</span>
              )}
            </div>

            {listLoading && (
              <div className="p-8 flex items-center justify-center">
                <div className="w-5 h-5 border-2 border-surface-border border-t-forest-900
                                rounded-full animate-spin" />
              </div>
            )}

            {!listLoading && listError && (
              <div className="p-5">
                <p className="text-sm text-red-600">{listError}</p>
              </div>
            )}

            {!listLoading && !listError && datasets.length === 0 && (
              <div className="p-8 text-center">
                <p className="text-sm text-text-muted">No datasets uploaded yet.</p>
                <p className="text-xs text-text-muted mt-1">
                  Upload a CSV or XLSX file to get started.
                </p>
              </div>
            )}

            {!listLoading && datasets.length > 0 && (
              <ul className="divide-y divide-surface-border">
                {datasets.map((ds) => (
                  <DatasetListItem
                    key={ds.id}
                    dataset={ds}
                    isSelected={selected?.id === ds.id}
                    onSelect={() => handleSelect(ds.id)}
                    onDelete={() => setDeleteTarget(ds.id)}
                  />
                ))}
              </ul>
            )}
          </div>
        </div>
      </div>

      {/* ── Delete confirmation modal ─────────────────────────── */}
      {deleteTarget && (
        <DeleteModal
          onConfirm={handleDelete}
          onCancel={() => setDeleteTarget(null)}
          loading={deleting}
        />
      )}
    </div>
  )
}


/* ─────────────────────────────────────────────────────────────────
   Sub-components
───────────────────────────────────────────────────────────────── */

function DatasetDetailPanel({
  dataset, preview, previewPage, previewLoading, onPageChange, onUploadAnother, onDelete,
}: {
  dataset:        DatasetDetail
  preview:        DatasetPreview | null
  previewPage:    number
  previewLoading: boolean
  onPageChange:   (p: number) => void
  onUploadAnother: () => void
  onDelete:       () => void
}) {
  const roles: Record<string, string> = JSON.parse(dataset.column_roles || '{}')
  const sensors  = Object.entries(roles).filter(([, r]) => r === 'sensor').map(([c]) => c)
  const sampleId = Object.entries(roles).filter(([, r]) => r === 'sample_id').map(([c]) => c)
  const category = Object.entries(roles).filter(([, r]) => r === 'category').map(([c]) => c)

  return (
    <div className="flex flex-col gap-4">
      {/* Header card */}
      <div className="border border-surface-border bg-brand-white">
        <div className="px-6 py-5 border-b border-surface-border
                        flex items-start justify-between gap-4 flex-wrap">
          <div>
            <h2 className="font-serif text-base text-text-primary mb-0.5">
              {dataset.original_filename}
            </h2>
            <p className="text-xs text-text-muted">
              {dataset.row_count} rows · {dataset.column_count} columns ·{' '}
              {(dataset.file_size_bytes / 1024).toFixed(1)} KB
            </p>
          </div>
          <div className="flex gap-2">
            <button
              onClick={onUploadAnother}
              className="text-xs px-3 py-1.5 border border-surface-border rounded-sm
                         text-text-secondary hover:text-text-primary hover:border-forest-900/30
                         transition-colors duration-150"
            >
              Upload another
            </button>
            <button
              onClick={onDelete}
              className="text-xs px-3 py-1.5 border border-red-200 rounded-sm
                         text-red-600 hover:bg-red-50 transition-colors duration-150"
            >
              Delete
            </button>
          </div>
        </div>

        {/* Stats */}
        <div className="grid grid-cols-3 divide-x divide-surface-border">
          <StatCell label="Sensor columns" value={String(dataset.sensor_column_count)} />
          <StatCell label="Missing values" value={String(dataset.missing_value_count)}
                    warn={dataset.missing_value_count > 0} />
          <StatCell label="Uploaded" value={new Date(dataset.created_at).toLocaleDateString()} />
        </div>

        {/* Role summary */}
        <div className="px-6 py-4 border-t border-surface-border">
          <p className="text-xs font-medium text-text-muted uppercase tracking-[0.1em] mb-3">
            Column roles
          </p>
          <div className="flex flex-col gap-2">
            <RoleRow icon="S" label="Sensors" cols={sensors} color="text-forest-900" />
            <RoleRow icon="ID" label="Sample ID" cols={sampleId} color="text-text-secondary" />
            <RoleRow icon="C" label="Category" cols={category} color="text-text-secondary" />
          </div>
        </div>
      </div>

      {/* Preview table */}
      {preview && (
        <div className="border border-surface-border bg-brand-white">
          <div className="px-6 py-4 border-b border-surface-border">
            <h3 className="font-serif text-base text-text-primary">Data Preview</h3>
            <p className="text-xs text-text-muted mt-0.5">
              Raw uploaded data — not preprocessed or modified.
            </p>
          </div>
          <DataPreviewTable
            preview={preview}
            page={previewPage}
            onPage={onPageChange}
            loading={previewLoading}
          />
        </div>
      )}
    </div>
  )
}

function StatCell({
  label, value, warn = false,
}: { label: string; value: string; warn?: boolean }) {
  return (
    <div className="px-6 py-4">
      <p className="text-xs text-text-muted mb-1">{label}</p>
      <p className={`text-sm font-medium ${warn ? 'text-amber-700' : 'text-text-primary'}`}>
        {value}
      </p>
    </div>
  )
}

function RoleRow({
  icon, label, cols, color,
}: { icon: string; label: string; cols: string[]; color: string }) {
  if (cols.length === 0) return null
  return (
    <div className="flex items-start gap-3">
      <span className={`text-[10px] font-bold font-mono w-5 shrink-0 ${color}`}>{icon}</span>
      <span className="text-xs text-text-muted w-20 shrink-0">{label}</span>
      <span className="text-xs text-text-secondary font-mono leading-relaxed">
        {cols.join(', ')}
      </span>
    </div>
  )
}

function DatasetListItem({
  dataset, isSelected, onSelect, onDelete,
}: {
  dataset:    DatasetSummary
  isSelected: boolean
  onSelect:   () => void
  onDelete:   () => void
}) {
  return (
    <li
      className={[
        'px-5 py-4 flex items-start justify-between gap-3 cursor-pointer',
        'transition-colors duration-150 group',
        isSelected ? 'bg-sage-100/60' : 'hover:bg-surface-overlay/50',
      ].join(' ')}
      onClick={onSelect}
    >
      <div className="min-w-0 flex-1">
        <p className="text-sm font-medium text-text-primary truncate">
          {dataset.original_filename}
        </p>
        <p className="text-xs text-text-muted mt-0.5">
          {dataset.row_count} rows · {dataset.sensor_column_count} sensors
        </p>
        {dataset.missing_value_count > 0 && (
          <p className="text-[10px] text-amber-700 mt-0.5">
            {dataset.missing_value_count} missing values
          </p>
        )}
      </div>
      <button
        onClick={(e) => { e.stopPropagation(); onDelete() }}
        className="shrink-0 text-xs text-text-muted hover:text-red-600
                   opacity-0 group-hover:opacity-100 transition-all duration-150 p-1"
        aria-label={`Delete ${dataset.original_filename}`}
      >
        <TrashIcon className="w-3.5 h-3.5" />
      </button>
    </li>
  )
}

function DeleteModal({
  onConfirm, onCancel, loading,
}: { onConfirm: () => void; onCancel: () => void; loading: boolean }) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-forest-900/40 backdrop-blur-sm"
        onClick={onCancel}
      />
      {/* Dialog */}
      <div className="relative bg-brand-white border border-surface-border rounded-sm
                      shadow-card-hover max-w-sm w-full p-6">
        <h3 className="font-serif text-lg text-text-primary mb-2">Delete dataset?</h3>
        <p className="text-sm text-text-secondary mb-6">
          The uploaded file and all associated metadata will be permanently removed.
          This cannot be undone.
        </p>
        <div className="flex gap-3 justify-end">
          <button
            onClick={onCancel}
            disabled={loading}
            className="px-4 py-2 text-sm border border-surface-border rounded-sm
                       text-text-secondary hover:text-text-primary hover:border-forest-900/30
                       transition-colors duration-150"
          >
            Cancel
          </button>
          <button
            onClick={onConfirm}
            disabled={loading}
            className="px-4 py-2 text-sm bg-red-600 text-white rounded-sm
                       hover:bg-red-700 transition-colors duration-150
                       disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {loading ? 'Deleting…' : 'Delete'}
          </button>
        </div>
      </div>
    </div>
  )
}


/* ── Icons ──────────────────────────────────────────────────────── */

function WarnIcon({ className = '' }: { className?: string }) {
  return (
    <svg viewBox="0 0 16 16" fill="none" className={className}
         xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
      <path d="M8 2L14.5 13.5H1.5L8 2Z" stroke="currentColor"
            strokeWidth="1.3" strokeLinejoin="round"/>
      <path d="M8 6.5v3M8 11v.5" stroke="currentColor"
            strokeWidth="1.5" strokeLinecap="round"/>
    </svg>
  )
}

function ErrorIcon({ className = '' }: { className?: string }) {
  return (
    <svg viewBox="0 0 16 16" fill="none" className={className}
         xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
      <circle cx="8" cy="8" r="6.5" stroke="currentColor" strokeWidth="1.3"/>
      <path d="M8 5v4M8 10.5v.5" stroke="currentColor"
            strokeWidth="1.5" strokeLinecap="round"/>
    </svg>
  )
}

function TrashIcon({ className = '' }: { className?: string }) {
  return (
    <svg viewBox="0 0 16 16" fill="none" className={className}
         xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
      <path d="M3 4h10M6 4V2.5h4V4M5 4l.5 9.5h5L11 4"
            stroke="currentColor" strokeWidth="1.3"
            strokeLinecap="round" strokeLinejoin="round"/>
    </svg>
  )
}
