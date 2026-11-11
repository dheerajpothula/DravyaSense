import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  type DatasetDetail,
  type DatasetSummary,
  type StatisticsResponse,
  ApiError,
  getDataset,
  getStatistics,
  listDatasets,
} from '../../api/datasets'
import {
  type ColumnStatsBeforeAfter,
  type ImputationStrategy,
  type OutlierAction,
  type PreprocessingConfig,
  type PreviewResponse,
  type ProcessedDatasetDetail,
  type ProcessedDatasetSummary,
  type ScalingMethod,
  applyPreprocessing,
  deleteProcessed,
  getProcessedDetail,
  getProcessedPreview,
  listProcessedDatasets,
  previewPreprocessing,
} from '../../api/preprocessing'
import PlotlyChart from '../../components/PlotlyChart'

/* ─────────────────────────────────────────────────────────────────
   Types
───────────────────────────────────────────────────────────────── */
type Phase =
  | 'idle'          // no dataset selected
  | 'configuring'   // dataset selected, building config
  | 'previewing'    // preview in-flight
  | 'previewed'     // preview result visible
  | 'applying'      // apply in-flight
  | 'applied'       // result saved, showing detail
  | 'error'

/* ─────────────────────────────────────────────────────────────────
   Formatting helpers
───────────────────────────────────────────────────────────────── */
function fmt(n: number | null | undefined, decimals = 3): string {
  if (n === null || n === undefined || Number.isNaN(n) || !Number.isFinite(n)) return '—'
  return n.toLocaleString('en-US', {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  })
}

/* ─────────────────────────────────────────────────────────────────
   Page component
───────────────────────────────────────────────────────────────── */
export default function PreprocessingPage() {
  /* ── Dataset list ─────────────────────────────────────────── */
  const [datasets,    setDatasets]    = useState<DatasetSummary[]>([])
  const [listLoading, setListLoading] = useState(true)
  const [listError,   setListError]   = useState<string | null>(null)

  /* ── Selected dataset ──────────────────────────────────────── */
  const [selectedId,   setSelectedId]   = useState<string | null>(null)
  const [detail,       setDetail]       = useState<DatasetDetail | null>(null)
  const [stats,        setStats]        = useState<StatisticsResponse | null>(null)
  const [statsLoading, setStatsLoading] = useState(false)

  /* ── Configuration ─────────────────────────────────────────── */
  const [selectedFeatures,  setSelectedFeatures]  = useState<string[]>([])
  const [imputation,        setImputation]        = useState<ImputationStrategy>('none')
  const [scaling,           setScaling]           = useState<ScalingMethod>('none')
  const [outlierAction,     setOutlierAction]     = useState<OutlierAction>('keep')
  const [iqrMultiplier,     setIqrMultiplier]     = useState<number>(1.5)

  /* ── Preview ───────────────────────────────────────────────── */
  const [preview,       setPreview]       = useState<PreviewResponse | null>(null)
  const [previewError,  setPreviewError]  = useState<string | null>(null)

  /* ── Apply ─────────────────────────────────────────────────── */
  const [applied,      setApplied]      = useState<ProcessedDatasetDetail | null>(null)
  const [applyError,   setApplyError]   = useState<string | null>(null)

  /* ── History ───────────────────────────────────────────────── */
  const [history,        setHistory]        = useState<ProcessedDatasetSummary[]>([])
  const [historyLoading, setHistoryLoading] = useState(false)
  const [historySelected, setHistorySelected] = useState<ProcessedDatasetDetail | null>(null)
  const [historyPreviewPage, setHistoryPreviewPage] = useState(1)
  const [historyPreview, setHistoryPreview] = useState<import('../../api/preprocessing').ProcessedDatasetPreview | null>(null)
  const [deletingId, setDeletingId] = useState<string | null>(null)

  /* ── Phase ─────────────────────────────────────────────────── */
  const [phase, setPhase] = useState<Phase>('idle')

  /* ── Derived ───────────────────────────────────────────────── */
  const sensorColumns = useMemo(() => {
    if (!detail) return []
    const roles: Record<string, string> = JSON.parse(detail.column_roles || '{}')
    return Object.entries(roles)
      .filter(([, r]) => r === 'sensor')
      .map(([c]) => c)
  }, [detail])

  const columnUnits = useMemo((): Record<string, string> => {
    if (!detail?.column_units) return {}
    try { return JSON.parse(detail.column_units) } catch { return {} }
  }, [detail])

  /* ── Load dataset list ────────────────────────────────────── */
  const refreshList = useCallback(async () => {
    setListLoading(true)
    setListError(null)
    try {
      const list = await listDatasets()
      setDatasets(list)
      if (list.length > 0 && !selectedId) setSelectedId(list[0].id)
    } catch {
      setListError('Could not load datasets. Is the backend running?')
    } finally {
      setListLoading(false)
    }
  }, [selectedId])

  useEffect(() => { refreshList() }, [refreshList])

  /* ── Load dataset detail + stats when selection changes ────── */
  useEffect(() => {
    if (!selectedId) return
    setDetail(null)
    setStats(null)
    setPreview(null)
    setApplied(null)
    setSelectedFeatures([])
    setPhase('configuring')
    setStatsLoading(true)
    Promise.all([getDataset(selectedId), getStatistics(selectedId)])
      .then(([d, s]) => {
        setDetail(d)
        setStats(s)
        // Default: select all sensor columns
        const roles: Record<string, string> = JSON.parse(d.column_roles || '{}')
        const sensors = Object.entries(roles)
          .filter(([, r]) => r === 'sensor')
          .map(([c]) => c)
        setSelectedFeatures(sensors)
        setStatsLoading(false)
      })
      .catch(() => {
        setPhase('error')
        setStatsLoading(false)
      })
  }, [selectedId])

  /* ── Load history when dataset changes ────────────────────── */
  useEffect(() => {
    if (!selectedId) return
    setHistoryLoading(true)
    listProcessedDatasets(selectedId)
      .then((h) => { setHistory(h); setHistoryLoading(false) })
      .catch(() => setHistoryLoading(false))
  }, [selectedId, applied])

  /* ── Build config ─────────────────────────────────────────── */
  const currentConfig: PreprocessingConfig = useMemo(() => ({
    selected_features:   selectedFeatures,
    imputation_strategy: imputation,
    scaling_method:      scaling,
    outlier_action:      outlierAction,
    iqr_multiplier:      iqrMultiplier,
  }), [selectedFeatures, imputation, scaling, outlierAction, iqrMultiplier])

  /* ── Preview ────────────────────────────────────────────────── */
  const handlePreview = useCallback(async () => {
    if (!selectedId || selectedFeatures.length === 0) return
    setPhase('previewing')
    setPreviewError(null)
    setPreview(null)
    try {
      const result = await previewPreprocessing(selectedId, currentConfig)
      setPreview(result)
      setPhase('previewed')
    } catch (err) {
      const msg = err instanceof ApiError ? err.message : 'Preview failed.'
      setPreviewError(msg)
      setPhase('configuring')
    }
  }, [selectedId, selectedFeatures, currentConfig])

  /* ── Apply ──────────────────────────────────────────────────── */
  const handleApply = useCallback(async () => {
    if (!selectedId || !preview) return
    setPhase('applying')
    setApplyError(null)
    try {
      const result = await applyPreprocessing(selectedId, currentConfig)
      setApplied(result)
      setPhase('applied')
    } catch (err) {
      const msg = err instanceof ApiError ? err.message : 'Apply failed.'
      setApplyError(msg)
      setPhase('previewed')
    }
  }, [selectedId, preview, currentConfig])

  /* ── History item selection ────────────────────────────────── */
  const handleSelectHistory = useCallback(async (id: string) => {
    try {
      const d = await getProcessedDetail(id)
      setHistorySelected(d)
      setHistoryPreviewPage(1)
      const pv = await getProcessedPreview(id, 1, 20)
      setHistoryPreview(pv)
    } catch { /* silent */ }
  }, [])

  const handleHistoryPageChange = useCallback(async (p: number) => {
    if (!historySelected) return
    const pv = await getProcessedPreview(historySelected.id, p, 20)
    setHistoryPreview(pv)
    setHistoryPreviewPage(p)
  }, [historySelected])

  /* ── Delete history item ────────────────────────────────────── */
  const handleDeleteHistory = useCallback(async (id: string) => {
    setDeletingId(id)
    try {
      await deleteProcessed(id)
      if (historySelected?.id === id) { setHistorySelected(null); setHistoryPreview(null) }
      if (selectedId) {
        const h = await listProcessedDatasets(selectedId)
        setHistory(h)
      }
    } catch { /* silent */ } finally {
      setDeletingId(null)
    }
  }, [historySelected, selectedId])

  /* ── Reset to reconfigure ──────────────────────────────────── */
  const handleReconfigure = useCallback(() => {
    setPreview(null)
    setApplied(null)
    setPreviewError(null)
    setApplyError(null)
    setPhase('configuring')
  }, [])

  /* ── Feature toggle ────────────────────────────────────────── */
  const toggleFeature = (col: string) => {
    setSelectedFeatures((prev) =>
      prev.includes(col) ? prev.filter((c) => c !== col) : [...prev, col]
    )
    // Reset preview when config changes
    if (phase === 'previewed') setPhase('configuring')
  }

  const toggleAll = () => {
    setSelectedFeatures(
      selectedFeatures.length === sensorColumns.length ? [] : [...sensorColumns]
    )
    if (phase === 'previewed') setPhase('configuring')
  }

  /* ─────────────────────────────────────────────────────────────
     Render
  ───────────────────────────────────────────────────────────────── */
  return (
    <div className="flex flex-col gap-8">

      {/* ── Page header ─────────────────────────────────────── */}
      <div className="pb-6 border-b border-surface-border">
        <p className="eyebrow mb-3">
          <span className="w-5 h-px bg-text-muted inline-block" />
          Module 03
        </p>
        <h1 className="font-serif text-display-sm text-text-primary mb-2 leading-tight">
          Preprocessing Studio
        </h1>
        <p className="text-text-secondary text-sm leading-relaxed max-w-xl">
          Configure imputation, outlier treatment and scaling for any uploaded dataset.
          Preview transformations before committing. Original data is never modified.
        </p>
      </div>

      {listLoading && <LoadingSpinner label="Loading datasets…" />}
      {listError && <ErrorBanner message={listError} />}

      {!listLoading && datasets.length === 0 && (
        <div className="border border-surface-border bg-brand-white p-8 text-center">
          <p className="text-sm text-text-muted">No datasets available.</p>
          <p className="text-xs text-text-muted mt-1">
            Upload a dataset in Dataset Management first.
          </p>
        </div>
      )}

      {!listLoading && datasets.length > 0 && (
        <div className="grid lg:grid-cols-5 gap-6">

          {/* ── Left: config panel (3/5) ─────────────────────── */}
          <div className="lg:col-span-3 flex flex-col gap-5">

            {/* Dataset selector */}
            <DatasetSelector
              datasets={datasets}
              selectedId={selectedId}
              onSelect={(id) => {
                setSelectedId(id)
                handleReconfigure()
              }}
            />

            {statsLoading && <LoadingSpinner label="Loading sensor data…" />}

            {!statsLoading && detail && stats && (
              <>
                {/* Dataset metadata strip */}
                <DatasetMetaStrip detail={detail} />

                {/* Feature selection */}
                <FeatureSelector
                  sensorColumns={sensorColumns}
                  selectedFeatures={selectedFeatures}
                  columnUnits={columnUnits}
                  onToggle={toggleFeature}
                  onToggleAll={toggleAll}
                  onChange={() => { if (phase === 'previewed') setPhase('configuring') }}
                />

                {/* Pipeline configuration */}
                <PipelineConfigPanel
                  imputation={imputation}
                  scaling={scaling}
                  outlierAction={outlierAction}
                  iqrMultiplier={iqrMultiplier}
                  onImputation={(v) => { setImputation(v); if (phase === 'previewed') setPhase('configuring') }}
                  onScaling={(v) => { setScaling(v); if (phase === 'previewed') setPhase('configuring') }}
                  onOutlier={(v) => { setOutlierAction(v); if (phase === 'previewed') setPhase('configuring') }}
                  onIqr={(v) => { setIqrMultiplier(v); if (phase === 'previewed') setPhase('configuring') }}
                />

                {/* Action bar */}
                <ActionBar
                  phase={phase}
                  canPreview={selectedFeatures.length > 0}
                  onPreview={handlePreview}
                  onApply={handleApply}
                  onReconfigure={handleReconfigure}
                  applyError={applyError}
                />
              </>
            )}

            {/* Preview error */}
            {previewError && (
              <div className="flex items-start gap-2 px-4 py-3
                              bg-red-50 border border-red-200 rounded-sm">
                <WarnIcon className="w-4 h-4 text-red-500 shrink-0 mt-0.5" />
                <p className="text-sm text-red-700">{previewError}</p>
              </div>
            )}
          </div>

          {/* ── Right: history sidebar (2/5) ─────────────────── */}
          <div className="lg:col-span-2">
            <ProcessingHistory
              history={history}
              loading={historyLoading}
              selected={historySelected}
              onSelect={handleSelectHistory}
              onDelete={handleDeleteHistory}
              deletingId={deletingId}
            />
          </div>
        </div>
      )}

      {/* ── Preview panel (full width below) ─────────────────── */}
      {(phase === 'previewing' || phase === 'previewed' || phase === 'applying' || phase === 'applied') && (
        <div className="flex flex-col gap-6">
          <div className="border-t border-surface-border pt-6">
            <h2 className="font-serif text-lg text-text-primary mb-1">
              {phase === 'applied' ? 'Applied Preprocessing' : 'Preview'}
            </h2>
            <p className="text-xs text-text-muted">
              {phase === 'applied'
                ? 'Processed data has been saved. Original dataset unchanged.'
                : 'In-memory preview only — no data has been saved yet.'}
            </p>
          </div>

          {phase === 'previewing' && <LoadingSpinner label="Running preview…" />}

          {preview && (phase === 'previewed' || phase === 'applying' || phase === 'applied') && (
            <PreviewPanel
              preview={preview}
              isApplied={phase === 'applied'}
              applied={applied}
            />
          )}
        </div>
      )}

      {/* ── History detail panel ─────────────────────────────── */}
      {historySelected && historyPreview && (
        <HistoryDetailPanel
          detail={historySelected}
          preview={historyPreview}
          previewPage={historyPreviewPage}
          onPageChange={handleHistoryPageChange}
          onClose={() => { setHistorySelected(null); setHistoryPreview(null) }}
        />
      )}
    </div>
  )
}

/* ─────────────────────────────────────────────────────────────────
   DatasetSelector
───────────────────────────────────────────────────────────────── */
function DatasetSelector({
  datasets, selectedId, onSelect,
}: {
  datasets: DatasetSummary[]
  selectedId: string | null
  onSelect: (id: string) => void
}) {
  return (
    <div className="border border-surface-border bg-brand-white">
      <div className="px-5 py-4 border-b border-surface-border">
        <h2 className="font-serif text-base text-text-primary">Select Dataset</h2>
      </div>
      <div className="p-5">
        <select
          value={selectedId ?? ''}
          onChange={(e) => onSelect(e.target.value)}
          className="w-full text-sm border border-surface-border bg-brand-white
                     text-text-primary rounded-sm px-3 py-2
                     focus:outline-none focus:border-forest-900/40 cursor-pointer"
        >
          {datasets.map((ds) => (
            <option key={ds.id} value={ds.id}>
              {ds.original_filename} — {ds.row_count} rows · {ds.sensor_column_count} sensors
              {ds.measurement_type ? ` · ${MEASUREMENT_LABELS[ds.measurement_type] ?? ds.measurement_type}` : ''}
            </option>
          ))}
        </select>
      </div>
    </div>
  )
}

/* ─────────────────────────────────────────────────────────────────
   DatasetMetaStrip
───────────────────────────────────────────────────────────────── */
function DatasetMetaStrip({ detail }: { detail: DatasetDetail }) {
  const roles: Record<string, string> = JSON.parse(detail.column_roles || '{}')
  const sampleIdCol = Object.entries(roles).find(([, r]) => r === 'sample_id')?.[0] ?? null
  const categoryCols = Object.entries(roles).filter(([, r]) => r === 'category').map(([c]) => c)
  const measureType = detail.measurement_type
    ? MEASUREMENT_LABELS[detail.measurement_type] ?? detail.measurement_type
    : null

  return (
    <div className="border border-surface-border bg-surface-overlay/40 rounded-sm px-5 py-3">
      <div className="flex flex-wrap gap-x-6 gap-y-1.5 text-xs">
        {measureType && (
          <MetaChip label="Type" value={measureType}
            className="text-forest-900 bg-forest-900/[0.06] border-forest-900/20" />
        )}
        <MetaChip label="Rows" value={String(detail.row_count)} />
        {sampleIdCol && <MetaChip label="ID column" value={sampleIdCol} mono />}
        {categoryCols.length > 0 && (
          <MetaChip label="Category" value={categoryCols.join(', ')} mono />
        )}
        {detail.missing_value_count > 0 && (
          <MetaChip label="Missing" value={String(detail.missing_value_count)}
            className="text-amber-700 bg-amber-50 border-amber-200" />
        )}
        {detail.source_attribution && (
          <span className="text-text-muted truncate max-w-xs"
            title={detail.source_attribution}>
            {detail.source_attribution}
          </span>
        )}
      </div>
    </div>
  )
}

function MetaChip({
  label, value, mono = false, className = '',
}: { label: string; value: string; mono?: boolean; className?: string }) {
  return (
    <span className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded-sm
                      border text-[11px] bg-brand-white border-surface-border ${className}`}>
      <span className="text-text-muted">{label}:</span>
      <span className={mono ? 'font-mono' : ''}>{value}</span>
    </span>
  )
}

/* ─────────────────────────────────────────────────────────────────
   FeatureSelector
───────────────────────────────────────────────────────────────── */
function FeatureSelector({
  sensorColumns, selectedFeatures, columnUnits, onToggle, onToggleAll, onChange: _onChange,
}: {
  sensorColumns:    string[]
  selectedFeatures: string[]
  columnUnits:      Record<string, string>
  onToggle:         (col: string) => void
  onToggleAll:      () => void
  onChange:         () => void
}) {
  const allSelected = selectedFeatures.length === sensorColumns.length
  const noneSelected = selectedFeatures.length === 0

  return (
    <div className="border border-surface-border bg-brand-white">
      <div className="px-5 py-4 border-b border-surface-border flex items-center justify-between gap-3">
        <div>
          <h3 className="font-serif text-base text-text-primary">Feature Selection</h3>
          <p className="text-xs text-text-muted mt-0.5">
            Only selected sensor columns will be transformed.
            sample_id and category columns are never modified.
          </p>
        </div>
        <button
          onClick={onToggleAll}
          className="text-xs px-3 py-1.5 border border-surface-border rounded-sm
                     text-text-secondary hover:text-text-primary hover:border-forest-900/30
                     transition-colors duration-150 shrink-0"
        >
          {allSelected ? 'Deselect all' : 'Select all'}
        </button>
      </div>

      <div className="p-5">
        {noneSelected && (
          <p className="text-xs text-amber-700 mb-3">
            Select at least one feature to enable preprocessing.
          </p>
        )}
        <div className="flex flex-wrap gap-2">
          {sensorColumns.map((col) => {
            const checked = selectedFeatures.includes(col)
            const unit = columnUnits[col]
            return (
              <button
                key={col}
                onClick={() => onToggle(col)}
                className={[
                  'inline-flex items-center gap-1.5 px-3 py-1.5 rounded-sm border',
                  'text-xs font-mono transition-colors duration-150',
                  checked
                    ? 'bg-forest-900 text-brand-white border-forest-900'
                    : 'bg-brand-white text-text-secondary border-surface-border hover:border-forest-900/30',
                ].join(' ')}
              >
                {col}
                {unit && (
                  <span className={`text-[9px] ${checked ? 'text-brand-white/70' : 'text-text-muted'}`}>
                    {unit}
                  </span>
                )}
              </button>
            )
          })}
        </div>
        <p className="text-xs text-text-muted mt-3">
          {selectedFeatures.length} of {sensorColumns.length} features selected
        </p>
      </div>
    </div>
  )
}

/* ─────────────────────────────────────────────────────────────────
   PipelineConfigPanel
───────────────────────────────────────────────────────────────── */
function PipelineConfigPanel({
  imputation, scaling, outlierAction, iqrMultiplier,
  onImputation, onScaling, onOutlier, onIqr,
}: {
  imputation:    ImputationStrategy
  scaling:       ScalingMethod
  outlierAction: OutlierAction
  iqrMultiplier: number
  onImputation:  (v: ImputationStrategy) => void
  onScaling:     (v: ScalingMethod) => void
  onOutlier:     (v: OutlierAction) => void
  onIqr:         (v: number) => void
}) {
  return (
    <div className="border border-surface-border bg-brand-white">
      <div className="px-5 py-4 border-b border-surface-border">
        <h3 className="font-serif text-base text-text-primary">Pipeline Configuration</h3>
        <p className="text-xs text-text-muted mt-0.5">
          Steps applied in order: imputation → outlier treatment → scaling.
        </p>
      </div>

      <div className="divide-y divide-surface-border">

        {/* Imputation */}
        <ConfigRow
          step="01"
          title="Missing Value Handling"
          desc="Fill NaN values in selected features. Zeros are not treated as missing."
        >
          <SegmentedControl
            value={imputation}
            onChange={onImputation as (v: string) => void}
            options={[
              { value: 'none',   label: 'None',   desc: 'Skip' },
              { value: 'mean',   label: 'Mean',   desc: 'Fill with column mean' },
              { value: 'median', label: 'Median', desc: 'Fill with column median' },
            ]}
          />
        </ConfigRow>

        {/* Outlier treatment */}
        <ConfigRow
          step="02"
          title="Outlier Treatment"
          desc="Based on IQR fence. Negative values are not treated as outliers."
        >
          <SegmentedControl
            value={outlierAction}
            onChange={onOutlier as (v: string) => void}
            options={[
              { value: 'keep',   label: 'Keep',   desc: 'No treatment' },
              { value: 'clip',   label: 'Clip',   desc: 'Clip to fence bounds' },
              { value: 'remove', label: 'Remove', desc: 'Remove outlier rows' },
            ]}
          />
          {outlierAction !== 'keep' && (
            <div className="flex items-center gap-3 mt-3">
              <label className="text-xs text-text-muted shrink-0">IQR multiplier</label>
              <input
                type="number"
                min={0.5}
                max={5}
                step={0.1}
                value={iqrMultiplier}
                onChange={(e) => onIqr(parseFloat(e.target.value) || 1.5)}
                className="w-24 text-sm border border-surface-border rounded-sm
                           px-3 py-1.5 bg-brand-white text-text-primary
                           focus:outline-none focus:border-forest-900/40 font-mono"
              />
              <span className="text-xs text-text-muted">
                Fence = Q3 + {iqrMultiplier}×IQR
              </span>
            </div>
          )}
        </ConfigRow>

        {/* Scaling */}
        <ConfigRow
          step="03"
          title="Scaling"
          desc="Applied to selected features after imputation and outlier treatment."
        >
          <SegmentedControl
            value={scaling}
            onChange={onScaling as (v: string) => void}
            options={[
              { value: 'none',     label: 'None',     desc: 'No scaling' },
              { value: 'standard', label: 'Standard', desc: '(x−μ)/σ — zero mean, unit variance' },
              { value: 'minmax',   label: 'Min-Max',  desc: 'Rescale to [0, 1]' },
              { value: 'robust',   label: 'Robust',   desc: '(x−median)/IQR — outlier resistant' },
            ]}
          />
        </ConfigRow>
      </div>
    </div>
  )
}

/* ─────────────────────────────────────────────────────────────────
   ActionBar
───────────────────────────────────────────────────────────────── */
function ActionBar({
  phase, canPreview, onPreview, onApply, onReconfigure, applyError,
}: {
  phase:         Phase
  canPreview:    boolean
  onPreview:     () => void
  onApply:       () => void
  onReconfigure: () => void
  applyError:    string | null
}) {
  const isPreviewing = phase === 'previewing'
  const isApplying   = phase === 'applying'
  const isPreviewed  = phase === 'previewed'
  const isApplied    = phase === 'applied'

  return (
    <div className="border border-surface-border bg-brand-white px-5 py-4">
      <div className="flex items-center gap-3 flex-wrap">

        {/* Preview button */}
        {(phase === 'configuring' || phase === 'previewing') && (
          <button
            onClick={onPreview}
            disabled={!canPreview || isPreviewing}
            className="inline-flex items-center gap-2 px-5 py-2 text-sm font-medium
                       border border-forest-900 text-forest-900 rounded-sm
                       hover:bg-forest-900/[0.06] transition-colors duration-150
                       disabled:opacity-40 disabled:cursor-not-allowed"
          >
            {isPreviewing
              ? <><SpinnerIcon className="w-4 h-4 animate-spin" />Running preview…</>
              : <><EyeIcon className="w-4 h-4" />Preview transformations</>
            }
          </button>
        )}

        {/* Previewed state: apply or reconfigure */}
        {(isPreviewed || isApplying) && (
          <>
            <button
              onClick={onApply}
              disabled={isApplying}
              className="inline-flex items-center gap-2 px-5 py-2 text-sm font-medium
                         bg-forest-900 text-brand-white rounded-sm
                         hover:bg-forest-800 transition-colors duration-150
                         disabled:opacity-40 disabled:cursor-not-allowed"
            >
              {isApplying
                ? <><SpinnerIcon className="w-4 h-4 animate-spin text-brand-white" />Saving…</>
                : <><SaveIcon className="w-4 h-4" />Apply &amp; save</>
              }
            </button>
            <button
              onClick={onReconfigure}
              disabled={isApplying}
              className="text-xs text-text-muted hover:text-text-primary
                         underline underline-offset-2 transition-colors duration-150"
            >
              ← Reconfigure
            </button>
          </>
        )}

        {/* Applied */}
        {isApplied && (
          <>
            <span className="inline-flex items-center gap-1.5 text-sm text-forest-900 font-medium">
              <CheckIcon className="w-4 h-4" />
              Processed dataset saved
            </span>
            <button
              onClick={onReconfigure}
              className="text-xs text-text-muted hover:text-text-primary
                         underline underline-offset-2 transition-colors duration-150"
            >
              ← Apply another configuration
            </button>
          </>
        )}

        {!canPreview && phase === 'configuring' && (
          <p className="text-xs text-amber-700">Select at least one feature first.</p>
        )}
      </div>

      {applyError && (
        <p className="text-xs text-red-600 mt-2">{applyError}</p>
      )}
    </div>
  )
}

/* ─────────────────────────────────────────────────────────────────
   PreviewPanel
───────────────────────────────────────────────────────────────── */
function PreviewPanel({
  preview, isApplied, applied,
}: {
  preview:   PreviewResponse
  isApplied: boolean
  applied:   ProcessedDatasetDetail | null
}) {
  // Processed units from backend (updated for scaled columns)
  const processedUnits = preview.processed_column_units ?? {}
  return (
    <div className="flex flex-col gap-6">

      {/* Summary row */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <SummaryCell label="Rows before"  value={String(preview.row_count_before)} />
        <SummaryCell label="Rows after"   value={String(preview.row_count_after)}
          warn={preview.row_count_after < preview.row_count_before} />
        <SummaryCell label="Features"     value={String(preview.selected_features.length)} />
        <SummaryCell label="Status"
          value={isApplied ? 'Saved ✓' : 'Preview only'}
          highlight={isApplied} />
      </div>

      {/* Applied dataset info */}
      {isApplied && applied && (
        <div className="flex items-center gap-3 px-5 py-3
                        bg-forest-900/[0.04] border border-forest-900/15 rounded-sm text-xs">
          <CheckIcon className="w-4 h-4 text-forest-900 shrink-0" />
          <div className="text-text-secondary">
            <span className="font-medium text-text-primary">Saved as processed dataset — </span>
            {applied.row_count} rows · {applied.sensor_column_count} sensor columns ·{' '}
            sklearn {applied.sklearn_version}
          </div>
        </div>
      )}

      {/* Transformations applied */}
      {preview.transformations_applied.length > 0 && (
        <div className="border border-surface-border bg-brand-white">
          <div className="px-5 py-3 border-b border-surface-border">
            <h3 className="font-serif text-sm text-text-primary">
              Transformations Applied ({preview.transformations_applied.length})
            </h3>
          </div>
          <ul className="px-5 py-3 flex flex-col gap-1.5">
            {preview.transformations_applied.map((t, i) => (
              <li key={i} className="flex items-start gap-2 text-sm text-text-secondary">
                <span className="w-4 h-4 rounded-full bg-forest-900/[0.08] text-forest-900
                                 text-[9px] font-bold flex items-center justify-center
                                 shrink-0 mt-0.5">
                  {i + 1}
                </span>
                {t}
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Warnings */}
      {preview.warnings.length > 0 && (
        <div className="flex flex-col gap-2">
          {preview.warnings.map((w, i) => (
            <div key={i} className="flex items-start gap-2 px-4 py-3
                                    bg-amber-50 border border-amber-200 rounded-sm">
              <WarnIcon className="w-4 h-4 text-amber-600 shrink-0 mt-0.5" />
              <p className="text-sm text-amber-800">{w}</p>
            </div>
          ))}
        </div>
      )}

      {/* Before / after stats comparison */}
      {preview.column_stats.length > 0 && (
        <BeforeAfterStatsTable stats={preview.column_stats} />
      )}

      {/* Before / after distribution charts */}
      {preview.column_stats.length > 0 && (
        <BeforeAfterCharts stats={preview.column_stats} previewRows={preview.preview_rows} columns={preview.columns} selectedFeatures={preview.selected_features} />
      )}

      {/* Preview data table */}
      <div className="border border-surface-border bg-brand-white">
        <div className="px-5 py-4 border-b border-surface-border flex items-center justify-between">
          <div>
            <h3 className="font-serif text-base text-text-primary">
              {isApplied ? 'Processed Data (first 10 rows)' : 'Preview Data (first 10 rows)'}
            </h3>
            <p className="text-xs text-text-muted mt-0.5">
              {isApplied
                ? 'Saved processed output — original data unchanged.'
                : 'In-memory preview only. Click "Apply & save" to commit.'}
            </p>
          </div>
          <PreviewBadge saved={isApplied} />
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-xs border-collapse">
            <thead>
              <tr className="bg-surface-overlay border-b border-surface-border">
                {preview.columns.map((col) => {
                  const isTransformed = preview.selected_features.includes(col)
                  const unit = processedUnits[col]
                  return (
                    <th key={col}
                      className={[
                        'px-4 py-2.5 text-left font-medium whitespace-nowrap',
                        'border-r border-surface-border last:border-r-0',
                        isTransformed ? 'text-forest-900' : 'text-text-muted',
                      ].join(' ')}>
                      <span>{col}</span>
                      {isTransformed && (
                        <span className="ml-1 text-[8px] text-forest-900/50">★</span>
                      )}
                      {unit && (
                        <span className={`block text-[9px] font-normal font-mono leading-tight mt-0.5 ${
                          isTransformed ? 'text-forest-900/60' : 'text-text-muted'
                        }`}>
                          {unit}
                        </span>
                      )}
                    </th>
                  )
                })}
              </tr>
            </thead>
            <tbody>
              {preview.preview_rows.map((row, ri) => (
                <tr key={ri}
                  className={`border-b border-surface-border last:border-0 ${ri % 2 === 0 ? 'bg-brand-white' : 'bg-surface-overlay/30'}`}>
                  {row.map((cell, ci) => (
                    <td key={ci}
                      className={[
                        'px-4 py-2 border-r border-surface-border last:border-r-0',
                        cell === null ? 'text-amber-600' : 'text-text-secondary font-mono',
                      ].join(' ')}>
                      {cell === null
                        ? <span className="italic font-mono text-[10px]">null</span>
                        : typeof cell === 'number'
                          ? cell.toFixed(5)
                          : String(cell)}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="px-5 py-2 text-xs text-text-muted border-t border-surface-border">
          ★ = transformed column · unit shown beneath column name · showing first {preview.preview_rows.length} rows
        </p>
      </div>
    </div>
  )
}

/* ─────────────────────────────────────────────────────────────────
   BeforeAfterStatsTable
───────────────────────────────────────────────────────────────── */
function BeforeAfterStatsTable({ stats }: { stats: ColumnStatsBeforeAfter[] }) {
  return (
    <div className="border border-surface-border bg-brand-white">
      <div className="px-5 py-4 border-b border-surface-border">
        <h3 className="font-serif text-base text-text-primary">Before / After Statistics</h3>
        <p className="text-xs text-text-muted mt-0.5">
          Per-feature summary before and after all transformations.
        </p>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-xs border-collapse">
          <thead>
            <tr className="bg-surface-overlay border-b border-surface-border">
              <th className="px-4 py-2.5 text-left font-medium text-text-muted
                             whitespace-nowrap sticky left-0 bg-surface-overlay">
                Feature
              </th>
              {['Mean', 'Std', 'Min', 'Max', 'Missing'].map((h) => (
                <th key={h + '-before'}
                  className="px-4 py-2.5 text-right font-medium text-text-muted whitespace-nowrap">
                  Before {h}
                </th>
              ))}
              {['Mean', 'Std', 'Min', 'Max', 'Missing'].map((h) => (
                <th key={h + '-after'}
                  className="px-4 py-2.5 text-right font-medium text-forest-900 whitespace-nowrap">
                  After {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {stats.map((s, i) => (
              <tr key={s.column}
                className={`border-b border-surface-border last:border-0 ${i % 2 === 0 ? 'bg-brand-white' : 'bg-surface-overlay/30'}`}>
                <td className={`px-4 py-2.5 font-mono font-medium text-text-primary
                               whitespace-nowrap sticky left-0
                               ${i % 2 === 0 ? 'bg-brand-white' : 'bg-surface-overlay/30'}`}>
                  {s.column}
                </td>
                <td className="px-4 py-2.5 text-right font-mono text-text-secondary">{fmt(s.before_mean)}</td>
                <td className="px-4 py-2.5 text-right font-mono text-text-secondary">{fmt(s.before_std)}</td>
                <td className="px-4 py-2.5 text-right font-mono text-text-secondary">{fmt(s.before_min)}</td>
                <td className="px-4 py-2.5 text-right font-mono text-text-secondary">{fmt(s.before_max)}</td>
                <td className={`px-4 py-2.5 text-right font-mono ${s.before_missing > 0 ? 'text-amber-700' : 'text-text-secondary'}`}>
                  {s.before_missing}
                </td>
                <td className="px-4 py-2.5 text-right font-mono text-forest-900">{fmt(s.after_mean)}</td>
                <td className="px-4 py-2.5 text-right font-mono text-forest-900">{fmt(s.after_std)}</td>
                <td className="px-4 py-2.5 text-right font-mono text-forest-900">{fmt(s.after_min)}</td>
                <td className="px-4 py-2.5 text-right font-mono text-forest-900">{fmt(s.after_max)}</td>
                <td className={`px-4 py-2.5 text-right font-mono ${s.after_missing > 0 ? 'text-amber-700' : 'text-forest-900'}`}>
                  {s.after_missing}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

/* ─────────────────────────────────────────────────────────────────
   BeforeAfterCharts
───────────────────────────────────────────────────────────────── */
function BeforeAfterCharts({
  stats, previewRows, columns, selectedFeatures,
}: {
  stats:            ColumnStatsBeforeAfter[]
  previewRows:      (string | number | null)[][]
  columns:          string[]
  selectedFeatures: string[]
}) {
  // Build per-column "after" value arrays from preview rows
  const afterData = useMemo(() => {
    const idx: Record<string, number> = {}
    columns.forEach((c, i) => { idx[c] = i })
    const out: Record<string, number[]> = {}
    for (const col of selectedFeatures) {
      if (idx[col] === undefined) continue
      const vals: number[] = []
      for (const row of previewRows) {
        const v = row[idx[col]]
        if (v !== null && typeof v === 'number') vals.push(v)
      }
      out[col] = vals
    }
    return out
  }, [previewRows, columns, selectedFeatures])

  const charts = useMemo(() => {
    return stats.map((s) => {
      const afterVals = afterData[s.column] ?? []
      if (afterVals.length === 0) return null

      // Compute histogram for after values
      const min = Math.min(...afterVals)
      const max = Math.max(...afterVals)
      const range = max - min
      const nBins = Math.min(15, Math.max(5, afterVals.length - 1))
      const binWidth = range === 0 ? 1 : range / nBins
      const counts = new Array(nBins).fill(0)
      const centers = Array.from({ length: nBins }, (_, i) => min + (i + 0.5) * binWidth)

      for (const v of afterVals) {
        const idx = range === 0 ? 0 : Math.min(Math.floor((v - min) / binWidth), nBins - 1)
        counts[idx]++
      }

      return { column: s.column, centers, counts }
    }).filter(Boolean) as { column: string; centers: number[]; counts: number[] }[]
  }, [stats, afterData])

  if (charts.length === 0) return null

  return (
    <div className="border border-surface-border bg-brand-white">
      <div className="px-5 py-4 border-b border-surface-border">
        <h3 className="font-serif text-base text-text-primary">
          After-Transformation Distributions
        </h3>
        <p className="text-xs text-text-muted mt-0.5">
          Histograms from preview rows. ★ = transformed features.
        </p>
      </div>
      <div className="p-4 grid sm:grid-cols-2 xl:grid-cols-3 gap-4">
        {charts.map(({ column, centers, counts }) => (
          <AfterChart key={column} column={column} centers={centers} counts={counts} />
        ))}
      </div>
    </div>
  )
}

function AfterChart({
  column, centers, counts,
}: { column: string; centers: number[]; counts: number[] }) {
  const data = useMemo(() => [{
    type: 'bar' as const,
    x: centers,
    y: counts,
    marker: { color: '#32493F', line: { color: '#1C2A22', width: 0.5 } },
  }], [centers, counts])

  const layout = useMemo(() => ({
    paper_bgcolor: 'rgba(0,0,0,0)',
    plot_bgcolor:  'rgba(0,0,0,0)',
    font: { family: 'Inter, system-ui, sans-serif', size: 9, color: '#4A5E50' },
    margin: { t: 8, r: 10, b: 36, l: 38 },
    bargap: 0.03,
    xaxis: {
      gridcolor: '#D2DCDB', linecolor: '#D2DCDB', zerolinecolor: '#D2DCDB',
      tickcolor: '#D2DCDB', tickfont: { size: 8 },
      title: { text: column, font: { size: 10, color: '#1C2A22' } },
    },
    yaxis: {
      gridcolor: '#D2DCDB', linecolor: '#D2DCDB', zerolinecolor: '#D2DCDB',
      tickcolor: '#D2DCDB', tickfont: { size: 8 },
      title: { text: 'Count', font: { size: 9, color: '#8A9E90' } },
    },
  }), [column])

  return (
    <div className="border border-surface-border">
      <div className="px-3 py-2 border-b border-surface-border flex items-center justify-between">
        <span className="font-mono text-xs font-medium text-text-primary">{column}</span>
        <span className="text-[9px] text-forest-900/60 font-medium">after ★</span>
      </div>
      <PlotlyChart data={data} layout={layout} style={{ width: '100%', height: 180 }} />
    </div>
  )
}

/* ─────────────────────────────────────────────────────────────────
   ProcessingHistory sidebar
───────────────────────────────────────────────────────────────── */
function ProcessingHistory({
  history, loading, selected, onSelect, onDelete, deletingId,
}: {
  history:     ProcessedDatasetSummary[]
  loading:     boolean
  selected:    ProcessedDatasetDetail | null
  onSelect:    (id: string) => void
  onDelete:    (id: string) => void
  deletingId:  string | null
}) {
  return (
    <div className="border border-surface-border bg-brand-white">
      <div className="px-5 py-4 border-b border-surface-border flex items-center justify-between">
        <h2 className="font-serif text-base text-text-primary">Processing History</h2>
        {!loading && (
          <span className="text-xs text-text-muted font-mono">{history.length}</span>
        )}
      </div>

      {loading && (
        <div className="p-6 flex justify-center">
          <SpinnerIcon className="w-5 h-5 animate-spin text-text-muted" />
        </div>
      )}

      {!loading && history.length === 0 && (
        <div className="p-6 text-center">
          <p className="text-xs text-text-muted">No processed datasets yet.</p>
          <p className="text-xs text-text-muted mt-1">
            Run a pipeline to save results here.
          </p>
        </div>
      )}

      {!loading && history.length > 0 && (
        <ul className="divide-y divide-surface-border">
          {history.map((item) => {
            const isSelected = selected?.id === item.id
            const features: string[] = (() => {
              try { return JSON.parse(item.selected_features) } catch { return [] }
            })()
            const date = new Date(item.created_at).toLocaleDateString('en-US', {
              month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit',
            })
            return (
              <li
                key={item.id}
                onClick={() => onSelect(item.id)}
                className={[
                  'px-5 py-4 cursor-pointer group transition-colors duration-150',
                  isSelected ? 'bg-sage-100/60' : 'hover:bg-surface-overlay/50',
                ].join(' ')}
              >
                <div className="flex items-start justify-between gap-2">
                  <div className="min-w-0 flex-1">
                    <p className="text-xs font-medium text-text-primary">
                      {item.row_count} rows · {item.sensor_column_count} features
                    </p>
                    <p className="text-[10px] text-text-muted mt-0.5 font-mono">
                      {features.slice(0, 3).join(', ')}{features.length > 3 ? ` +${features.length - 3}` : ''}
                    </p>
                    <p className="text-[10px] text-text-muted mt-0.5">{date}</p>
                  </div>
                  <button
                    onClick={(e) => { e.stopPropagation(); onDelete(item.id) }}
                    disabled={deletingId === item.id}
                    className="shrink-0 text-text-muted hover:text-red-600
                               opacity-0 group-hover:opacity-100 transition-all duration-150 p-1"
                    aria-label="Delete processed dataset"
                  >
                    {deletingId === item.id
                      ? <SpinnerIcon className="w-3.5 h-3.5 animate-spin" />
                      : <TrashIcon className="w-3.5 h-3.5" />
                    }
                  </button>
                </div>
              </li>
            )
          })}
        </ul>
      )}
    </div>
  )
}

/* ─────────────────────────────────────────────────────────────────
   HistoryDetailPanel
───────────────────────────────────────────────────────────────── */
function HistoryDetailPanel({
  detail, preview, previewPage, onPageChange, onClose,
}: {
  detail:       ProcessedDatasetDetail
  preview:      import('../../api/preprocessing').ProcessedDatasetPreview
  previewPage:  number
  onPageChange: (p: number) => void
  onClose:      () => void
}) {
  const config = (() => { try { return JSON.parse(detail.pipeline_config) } catch { return {} } })()
  const transforms: string[] = (() => {
    try { return JSON.parse(detail.transformations_applied) } catch { return [] }
  })()
  const features: string[] = (() => {
    try { return JSON.parse(detail.selected_features) } catch { return [] }
  })()
  const units = (() => {
    try { return JSON.parse(detail.column_units || '{}') } catch { return {} }
  })() as Record<string, string>

  const totalPages = Math.ceil(preview.total_rows / preview.page_size)
  const start = (previewPage - 1) * preview.page_size + 1
  const end   = Math.min(previewPage * preview.page_size, preview.total_rows)

  return (
    <div className="border border-surface-border bg-brand-white mt-2">
      <div className="px-6 py-5 border-b border-surface-border
                      flex items-start justify-between gap-4">
        <div>
          <h3 className="font-serif text-base text-text-primary">Processed Dataset Detail</h3>
          <p className="text-xs text-text-muted mt-0.5">
            Source: {detail.source_filename} · {detail.row_count} rows ·{' '}
            {detail.sensor_column_count} features · sklearn {detail.sklearn_version}
          </p>
        </div>
        <button
          onClick={onClose}
          className="text-xs text-text-muted hover:text-text-primary
                     underline underline-offset-2 transition-colors duration-150"
        >
          Close
        </button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-0 divide-y md:divide-y-0 md:divide-x divide-surface-border">
        {/* Config summary */}
        <div className="px-6 py-5">
          <p className="text-xs font-medium text-text-muted uppercase tracking-[0.1em] mb-3">
            Pipeline Configuration
          </p>
          <div className="flex flex-col gap-2 text-xs">
            <ConfigPill label="Imputation" value={config.imputation_strategy ?? '—'} />
            <ConfigPill label="Outlier"    value={`${config.outlier_action ?? '—'}${config.outlier_action !== 'keep' ? ` (IQR×${config.iqr_multiplier})` : ''}`} />
            <ConfigPill label="Scaling"    value={config.scaling_method ?? '—'} />
          </div>
          <div className="mt-4">
            <p className="text-xs font-medium text-text-muted uppercase tracking-[0.1em] mb-2">
              Features ({features.length})
            </p>
            <div className="flex flex-wrap gap-1.5">
              {features.map((f) => (
                <span key={f}
                  className="inline-flex items-center gap-1 px-2 py-0.5
                             bg-surface-overlay border border-surface-border
                             rounded-sm text-[10px] font-mono">
                  {f}
                  {units[f] && <span className="text-text-muted">· {units[f]}</span>}
                </span>
              ))}
            </div>
          </div>
          {transforms.length > 0 && (
            <div className="mt-4">
              <p className="text-xs font-medium text-text-muted uppercase tracking-[0.1em] mb-2">
                Applied Steps
              </p>
              <ul className="flex flex-col gap-1">
                {transforms.map((t, i) => (
                  <li key={i} className="text-xs text-text-secondary">
                    {i + 1}. {t}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>

        {/* Warnings from config */}
        <div className="px-6 py-5">
          <p className="text-xs font-medium text-text-muted uppercase tracking-[0.1em] mb-3">
            Processing Notes
          </p>
          <div className="flex flex-col gap-1.5 text-xs text-text-secondary">
            <div className="flex gap-2">
              <span className="text-text-muted shrink-0">Missing values:</span>
              <span className={detail.missing_value_count > 0 ? 'text-amber-700' : ''}>
                {detail.missing_value_count}
              </span>
            </div>
            <div className="flex gap-2">
              <span className="text-text-muted shrink-0">File size:</span>
              <span>{(detail.file_size_bytes / 1024).toFixed(1)} KB</span>
            </div>
            <div className="flex gap-2">
              <span className="text-text-muted shrink-0">Created:</span>
              <span>{new Date(detail.created_at).toLocaleString()}</span>
            </div>
          </div>
          {(config.warnings ?? []).length > 0 && (
            <div className="mt-3 flex flex-col gap-1">
              {(config.warnings as string[]).map((w, i) => (
                <p key={i} className="text-[11px] text-amber-700 flex items-start gap-1.5">
                  <WarnIcon className="w-3 h-3 shrink-0 mt-0.5" /> {w}
                </p>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Processed data preview */}
      <div className="border-t border-surface-border">
        <div className="px-6 py-4 border-b border-surface-border">
          <h4 className="font-serif text-sm text-text-primary">Processed Data Preview</h4>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-xs border-collapse">
            <thead>
              <tr className="bg-surface-overlay border-b border-surface-border">
                <th className="px-4 py-2.5 text-right text-text-muted font-medium w-10 border-r border-surface-border">#</th>
                {preview.columns.map((col) => (
                  <th key={col}
                    className={[
                      'px-4 py-2.5 text-left font-medium whitespace-nowrap',
                      'border-r border-surface-border last:border-r-0',
                      features.includes(col) ? 'text-forest-900' : 'text-text-muted',
                    ].join(' ')}>
                    {col}
                    {units[col] && (
                      <span className={`block text-[9px] font-normal font-mono leading-tight mt-0.5 ${
                        features.includes(col) ? 'text-forest-900/60' : 'text-text-muted'
                      }`}>
                        {units[col]}
                      </span>
                    )}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {preview.rows.map((row, ri) => (
                <tr key={ri}
                  className={`border-b border-surface-border last:border-0 ${ri % 2 === 0 ? 'bg-brand-white' : 'bg-surface-overlay/30'}`}>
                  <td className="px-4 py-2 text-right font-mono text-text-muted border-r border-surface-border">
                    {start + ri}
                  </td>
                  {row.map((cell, ci) => (
                    <td key={ci}
                      className="px-4 py-2 border-r border-surface-border last:border-r-0 text-text-secondary font-mono">
                      {cell === null
                        ? <span className="italic text-amber-600 text-[10px]">null</span>
                        : typeof cell === 'number'
                          ? cell.toFixed(4)
                          : String(cell)}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="flex items-center justify-between px-4 py-3
                        border-t border-surface-border bg-surface-overlay/40">
          <p className="text-xs text-text-muted">Rows {start}–{end} of {preview.total_rows}</p>
          <div className="flex items-center gap-1">
            <PaginationBtn label="‹ Prev" disabled={previewPage <= 1}
              onClick={() => onPageChange(previewPage - 1)} />
            <span className="px-3 py-1 text-xs text-text-muted">
              {previewPage} / {totalPages}
            </span>
            <PaginationBtn label="Next ›" disabled={previewPage >= totalPages}
              onClick={() => onPageChange(previewPage + 1)} />
          </div>
        </div>
      </div>
    </div>
  )
}

/* ─────────────────────────────────────────────────────────────────
   Small reusable sub-components
───────────────────────────────────────────────────────────────── */

function SegmentedControl({
  value, onChange, options,
}: {
  value:    string
  onChange: (v: string) => void
  options:  { value: string; label: string; desc: string }[]
}) {
  return (
    <div className="flex flex-wrap gap-2">
      {options.map((opt) => (
        <button
          key={opt.value}
          onClick={() => onChange(opt.value)}
          title={opt.desc}
          className={[
            'px-3 py-1.5 text-xs border rounded-sm transition-colors duration-150',
            value === opt.value
              ? 'bg-forest-900 text-brand-white border-forest-900'
              : 'bg-brand-white text-text-secondary border-surface-border hover:border-forest-900/30',
          ].join(' ')}
        >
          {opt.label}
        </button>
      ))}
    </div>
  )
}

function ConfigRow({
  step, title, desc, children,
}: { step: string; title: string; desc: string; children: React.ReactNode }) {
  return (
    <div className="px-5 py-4">
      <div className="flex items-start gap-3 mb-3">
        <span className="text-[9px] font-bold font-mono text-text-muted
                         w-5 h-5 rounded-full border border-surface-border
                         flex items-center justify-center shrink-0 mt-0.5">
          {step}
        </span>
        <div>
          <p className="text-sm font-medium text-text-primary">{title}</p>
          <p className="text-xs text-text-muted mt-0.5">{desc}</p>
        </div>
      </div>
      <div className="pl-8">{children}</div>
    </div>
  )
}

function SummaryCell({
  label, value, warn = false, highlight = false,
}: { label: string; value: string; warn?: boolean; highlight?: boolean }) {
  return (
    <div className="border border-surface-border bg-brand-white px-5 py-4">
      <p className="text-xs text-text-muted mb-1">{label}</p>
      <p className={`text-sm font-medium font-mono
                     ${warn ? 'text-amber-700' : highlight ? 'text-forest-900' : 'text-text-primary'}`}>
        {value}
      </p>
    </div>
  )
}

function ConfigPill({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center gap-2">
      <span className="text-text-muted w-20 shrink-0">{label}:</span>
      <span className="font-mono text-text-primary">{value}</span>
    </div>
  )
}

function PreviewBadge({ saved }: { saved: boolean }) {
  return saved ? (
    <span className="inline-flex items-center gap-1 px-2 py-0.5 text-[10px] font-medium
                     tracking-wide uppercase rounded-sm border
                     bg-forest-900/[0.07] text-forest-900 border-forest-900/20">
      Saved
    </span>
  ) : (
    <span className="inline-flex items-center gap-1 px-2 py-0.5 text-[10px] font-medium
                     tracking-wide uppercase rounded-sm border
                     bg-amber-50 text-amber-700 border-amber-200">
      Preview only
    </span>
  )
}

function LoadingSpinner({ label }: { label: string }) {
  return (
    <div className="border border-surface-border bg-brand-white p-8
                    flex items-center justify-center gap-3">
      <SpinnerIcon className="w-5 h-5 animate-spin text-text-muted" />
      <p className="text-sm text-text-secondary">{label}</p>
    </div>
  )
}

function ErrorBanner({ message }: { message: string }) {
  return (
    <div className="flex items-start gap-2 px-4 py-3
                    bg-red-50 border border-red-200 rounded-sm">
      <WarnIcon className="w-4 h-4 text-red-500 shrink-0 mt-0.5" />
      <p className="text-sm text-red-700">{message}</p>
    </div>
  )
}

function PaginationBtn({
  label, onClick, disabled,
}: { label: string; onClick: () => void; disabled: boolean }) {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      className={[
        'px-3 py-1 text-xs border border-surface-border rounded-sm',
        disabled
          ? 'text-text-muted cursor-not-allowed'
          : 'text-text-primary hover:bg-surface-overlay cursor-pointer',
      ].join(' ')}
    >
      {label}
    </button>
  )
}

/* ─────────────────────────────────────────────────────────────────
   Constants
───────────────────────────────────────────────────────────────── */
const MEASUREMENT_LABELS: Record<string, string> = {
  electronic_tongue: 'Electronic Tongue',
  electronic_nose:   'Electronic Nose',
  chemical_analysis: 'Chemical Analysis',
}

/* ─────────────────────────────────────────────────────────────────
   Icons
───────────────────────────────────────────────────────────────── */
function SpinnerIcon({ className = '' }: { className?: string }) {
  return (
    <svg className={className} xmlns="http://www.w3.org/2000/svg"
         fill="none" viewBox="0 0 24 24" aria-hidden="true">
      <circle className="opacity-25" cx="12" cy="12" r="10"
        stroke="currentColor" strokeWidth="4"/>
      <path className="opacity-75" fill="currentColor"
        d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"/>
    </svg>
  )
}

function EyeIcon({ className = '' }: { className?: string }) {
  return (
    <svg viewBox="0 0 16 16" fill="none" className={className}
         xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
      <path d="M1 8s2.5-5 7-5 7 5 7 5-2.5 5-7 5-7-5-7-5Z"
        stroke="currentColor" strokeWidth="1.3"/>
      <circle cx="8" cy="8" r="2" stroke="currentColor" strokeWidth="1.3"/>
    </svg>
  )
}

function SaveIcon({ className = '' }: { className?: string }) {
  return (
    <svg viewBox="0 0 16 16" fill="none" className={className}
         xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
      <rect x="2" y="2" width="12" height="12" rx="1"
        stroke="currentColor" strokeWidth="1.3"/>
      <path d="M5 2v4h6V2M8 9v4" stroke="currentColor" strokeWidth="1.3"
        strokeLinecap="round"/>
    </svg>
  )
}

function CheckIcon({ className = '' }: { className?: string }) {
  return (
    <svg viewBox="0 0 16 16" fill="none" className={className}
         xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
      <path d="M3 8l4 4 6-7" stroke="currentColor" strokeWidth="1.5"
        strokeLinecap="round" strokeLinejoin="round"/>
    </svg>
  )
}

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

function TrashIcon({ className = '' }: { className?: string }) {
  return (
    <svg viewBox="0 0 16 16" fill="none" className={className}
         xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
      <path d="M3 4h10M6 4V2.5a.5.5 0 01.5-.5h3a.5.5 0 01.5.5V4M5 4l.5 9h5l.5-9"
        stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" strokeLinejoin="round"/>
    </svg>
  )
}

/* ─────────────────────────────────────────────────────────────────
   End of file
───────────────────────────────────────────────────────────────── */
