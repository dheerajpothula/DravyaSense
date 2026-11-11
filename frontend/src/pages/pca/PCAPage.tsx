import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  type DatasetDetail,
  type DatasetSummary,
  getDataset,
  listDatasets,
} from '../../api/datasets'
import {
  type ProcessedDatasetDetail,
  type ProcessedDatasetSummary,
  getProcessedDetail,
  listProcessedDatasets,
} from '../../api/preprocessing'
import {
  type InputType,
  type PcaExperimentSummary,
  type PcaResult,
  type PcaRunRequest,
  ApiError as PcaApiError,
  deletePcaExperiment,
  getPcaExperiment,
  listPcaExperiments,
  runPca,
  savePca,
} from '../../api/pca'
import PlotlyChart from '../../components/PlotlyChart'

/* ─────────────────────────────────────────────────────────────────
   Helpers
───────────────────────────────────────────────────────────────── */
function fmt(n: number | null | undefined, decimals = 4): string {
  if (n === null || n === undefined || Number.isNaN(n) || !Number.isFinite(n)) return '—'
  return n.toLocaleString('en-US', { minimumFractionDigits: decimals, maximumFractionDigits: decimals })
}

/** Convert a raw source filename into a human-readable dataset label. */
function prettyDatasetName(filename: string): string {
  const base = filename.replace(/\.csv$/i, '')
  // Common patterns: magnolia_electronic_tongue → Magnolia E-tongue
  return base
    .replace(/_electronic_tongue/i, ' E-tongue')
    .replace(/_electronic_nose/i, ' E-nose')
    .replace(/_chemical_analysis/i, ' Chemical')
    .replace(/^magnolia_/, 'Magnolia ')
    .replace(/_/g, ' ')
}

/** Convert a raw scaling_method value into a display label. */
function scalerLabel(method: string | null | undefined): string {
  switch (method) {
    case 'standard': return 'StandardScaler'
    case 'minmax':   return 'MinMaxScaler'
    case 'robust':   return 'RobustScaler'
    case 'none':     return 'No scaling'
    default:         return 'Unknown scaler'
  }
}

function downloadCsv(filename: string, csvContent: string) {
  const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  link.click()
  URL.revokeObjectURL(url)
}

/* ─────────────────────────────────────────────────────────────────
   Color palette for category labels
───────────────────────────────────────────────────────────────── */
const CATEGORY_COLORS: Record<string, string> = {
  JYHP: '#2D4A3E',
  AYHP: '#C25E3A',
}
const FALLBACK_COLORS = ['#32493F', '#8A9E90', '#C25E3A', '#5A8A7A', '#D2DCDB', '#1C2A22']
function colorFor(label: string, idx: number): string {
  return CATEGORY_COLORS[label] ?? FALLBACK_COLORS[idx % FALLBACK_COLORS.length]
}

/* ─────────────────────────────────────────────────────────────────
   Phase
───────────────────────────────────────────────────────────────── */
type Phase = 'idle' | 'configuring' | 'running' | 'results' | 'error'

/* ═════════════════════════════════════════════════════════════════
   Main Page Component
═════════════════════════════════════════════════════════════════ */
export default function PCAPage() {
  // ── Dataset list ──────────────────────────────────────────────
  const [datasets, setDatasets] = useState<DatasetSummary[]>([])
  const [listLoading, setListLoading] = useState(true)

  // ── Input selection ───────────────────────────────────────────
  const [inputType, setInputType] = useState<InputType>('raw_dataset')
  const [selectedRawId, setSelectedRawId] = useState<string | null>(null)
  const [processedList, setProcessedList] = useState<ProcessedDatasetSummary[]>([])
  const [selectedProcessedId, setSelectedProcessedId] = useState<string | null>(null)
  const [processedDetail, setProcessedDetail] = useState<ProcessedDatasetDetail | null>(null)

  // ── Dataset detail (for feature selection) ───────────────────
  const [detail, setDetail] = useState<DatasetDetail | null>(null)

  // ── Config ────────────────────────────────────────────────────
  const [nComponents, setNComponents] = useState(4)
  const [selectedFeatures, setSelectedFeatures] = useState<string[]>([])
  const [experimentName, setExperimentName] = useState('')

  // ── Results ───────────────────────────────────────────────────
  const [result, setResult] = useState<PcaResult | null>(null)
  const [running, setRunning] = useState(false)
  const [error, setError] = useState<string | null>(null)
  // Tracks whether the current result came from loading a saved
  // historical experiment (true) or a fresh run (false).  Used to
  // display a clear "Loaded Experiment" indicator and ensure the
  // results are not confused with the currently selected input.
  const [isLoadedExperiment, setIsLoadedExperiment] = useState(false)

  // ── Experiment history ────────────────────────────────────────
  const [experiments, setExperiments] = useState<PcaExperimentSummary[]>([])
  const [historyLoading, setHistoryLoading] = useState(false)
  const [deletingId, setDeletingId] = useState<string | null>(null)

  // ── Phase ─────────────────────────────────────────────────────
  const [phase, setPhase] = useState<Phase>('idle')

  /* ── Derived values ──────────────────────────────────────────── */
  const sensorColumns = useMemo(() => {
    if (!detail) return []
    const roles: Record<string, string> = JSON.parse(detail.column_roles || '{}')
    return Object.entries(roles).filter(([, r]) => r === 'sensor').map(([c]) => c)
  }, [detail])

  const categoryColumns = useMemo(() => {
    if (!detail) return []
    const roles: Record<string, string> = JSON.parse(detail.column_roles || '{}')
    return Object.entries(roles).filter(([, r]) => r === 'category').map(([c]) => c)
  }, [detail])

  const columnUnits = useMemo((): Record<string, string> => {
    if (!detail?.column_units) return {}
    try { return JSON.parse(detail.column_units) } catch { return {} }
  }, [detail])

  const maxComponents = useMemo(() => {
    if (!detail) return 2
    return Math.min(detail.row_count, sensorColumns.length)
  }, [detail, sensorColumns])

  /* ── Load dataset list ──────────────────────────────────────── */
  useEffect(() => {
    listDatasets()
      .then((list) => {
        setDatasets(list)
        setListLoading(false)
        // Prefer the Magnolia Electronic Tongue dataset as the initial
        // selection — identified by measurement_type + research source
        // attribution.  Fallback: any electronic-tongue dataset, then the
        // first available.  This never overrides an explicit user choice
        // because it only runs once on mount.
        const preferred =
          list.find((d) =>
            d.measurement_type === 'electronic_tongue' &&
            (d.source_attribution?.toLowerCase().includes('magnolia') ||
             d.original_filename.toLowerCase().includes('magnolia'))
          ) ??
          list.find((d) => d.measurement_type === 'electronic_tongue') ??
          list[0]
        if (preferred) setSelectedRawId(preferred.id)
      })
      .catch(() => { setListLoading(false) })
  }, [])

  /* ── Load dataset detail when raw selection changes ─────────── */
  useEffect(() => {
    if (!selectedRawId || inputType !== 'raw_dataset') return
    setDetail(null)
    getDataset(selectedRawId)
      .then((d) => {
        setDetail(d)
        const roles: Record<string, string> = JSON.parse(d.column_roles || '{}')
        const sensors = Object.entries(roles).filter(([, r]) => r === 'sensor').map(([c]) => c)
        setSelectedFeatures(sensors)
        setNComponents(Math.min(4, Math.min(d.row_count, sensors.length)))
        setPhase('configuring')
      })
      .catch(() => { setPhase('error') })
  }, [selectedRawId, inputType])

  /* ── Load processed datasets when switching to processed ────── */
  useEffect(() => {
    if (inputType !== 'processed_dataset' || !selectedRawId) return
    listProcessedDatasets(selectedRawId)
      .then((list) => {
        setProcessedList(list)
        if (list.length > 0) {
          setSelectedProcessedId(list[0].id)
          // Load the source dataset detail to get sensor info
          getDataset(selectedRawId)
            .then((d) => {
              setDetail(d)
              const roles: Record<string, string> = JSON.parse(d.column_roles || '{}')
              const sensors = Object.entries(roles).filter(([, r]) => r === 'sensor').map(([c]) => c)
              // Use selected_features from the processed dataset
              const procFeats: string[] = (() => {
                try { return JSON.parse(list[0].selected_features) } catch { return sensors }
              })()
              setSelectedFeatures(procFeats)
              setNComponents(Math.min(4, Math.min(d.row_count, procFeats.length)))
              setPhase('configuring')
            })
            .catch(() => { setPhase('error') })
        } else {
          setPhase('idle')
        }
      })
      .catch(() => { setHistoryLoading(false) })
  }, [inputType, selectedRawId])

  /* ── Update features when processed selection changes ───────── */
  useEffect(() => {
    if (inputType !== 'processed_dataset' || !selectedProcessedId || processedList.length === 0) return
    const proc = processedList.find((p) => p.id === selectedProcessedId)
    if (!proc) return
    const feats: string[] = (() => { try { return JSON.parse(proc.selected_features) } catch { return [] } })()
    setSelectedFeatures(feats)
    setNComponents(Math.min(4, Math.min(proc.row_count, feats.length)))
    // Fetch the processed dataset detail to display its preprocessing config
    getProcessedDetail(selectedProcessedId)
      .then((d) => setProcessedDetail(d))
      .catch(() => setProcessedDetail(null))
  }, [selectedProcessedId, processedList, inputType])

  /* ── Load experiment history ────────────────────────────────── */
  const refreshHistory = useCallback(async () => {
    setHistoryLoading(true)
    try {
      const list = await listPcaExperiments()
      setExperiments(list)
    } catch { /* silent */ } finally {
      setHistoryLoading(false)
    }
  }, [])

  useEffect(() => { refreshHistory() }, [refreshHistory])

  /* ── Run PCA ────────────────────────────────────────────────── */
  const handleRun = useCallback(async (save: boolean) => {
    const inputId = inputType === 'raw_dataset' ? selectedRawId : selectedProcessedId
    if (!inputId) return
    setRunning(true)
    setError(null)
    setPhase('running')
    setIsLoadedExperiment(false)   // fresh run — not a loaded experiment

    const req: PcaRunRequest = {
      input_type: inputType,
      input_id: inputId,
      n_components: nComponents,
      feature_columns: selectedFeatures.length > 0 ? selectedFeatures : null,
      experiment_name: save ? (experimentName.trim() || null) : null,
    }

    try {
      const r = save ? await savePca(req) : await runPca(req)
      setResult(r)
      setPhase('results')
      if (save) refreshHistory()
    } catch (err) {
      const msg = err instanceof PcaApiError ? err.message : 'PCA computation failed.'
      setError(msg)
      setPhase('error')
    } finally {
      setRunning(false)
    }
  }, [inputType, selectedRawId, selectedProcessedId, nComponents, selectedFeatures, experimentName, refreshHistory])

  /* ── Load saved experiment ──────────────────────────────────── */
  const handleLoadExperiment = useCallback(async (id: string) => {
    setRunning(true)
    setError(null)
    try {
      const r = await getPcaExperiment(id)
      setResult(r)
      setPhase('results')
      setIsLoadedExperiment(true)   // result came from history, not a run

      // ── Restore the loaded experiment's original configuration ──
      // This ensures the input selector reflects what was actually
      // analysed and that "Reconfigure" returns to the experiment's
      // original settings rather than the stale pre-load state.
      if (r.input_type === 'raw_dataset') {
        setInputType('raw_dataset')
        setSelectedRawId(r.input_id)
      } else {
        setInputType('processed_dataset')
        setSelectedProcessedId(r.input_id)
      }
      if (r.feature_columns && r.feature_columns.length > 0) {
        setSelectedFeatures(r.feature_columns)
      }
      setNComponents(r.n_components)
      if (r.experiment_name) setExperimentName(r.experiment_name)
    } catch (err) {
      setError(err instanceof PcaApiError ? err.message : 'Could not load experiment.')
      setPhase('error')
    } finally {
      setRunning(false)
    }
  }, [])

  /* ── Delete experiment ─────────────────────────────────────── */
  const handleDeleteExperiment = useCallback(async (id: string) => {
    setDeletingId(id)
    try {
      await deletePcaExperiment(id)
      await refreshHistory()
    } catch { /* silent */ } finally {
      setDeletingId(null)
    }
  }, [refreshHistory])

  /* ── Feature toggle ─────────────────────────────────────────── */
  const toggleFeature = (col: string) => {
    setSelectedFeatures((prev) =>
      prev.includes(col) ? prev.filter((c) => c !== col) : [...prev, col]
    )
  }
  const toggleAll = () => {
    setSelectedFeatures(selectedFeatures.length === sensorColumns.length ? [] : [...sensorColumns])
  }

  /* ── Export CSV ──────────────────────────────────────────────── */
  const exportScores = () => {
    if (!result) return
    const header = ['sample_id', 'category', ...Array.from({ length: result.n_components }, (_, i) => `PC${i + 1}`)]
    const rows = result.sample_ids.map((sid, i) => {
      const cat = result.category_labels[i] || ''
      const pcs = result.scores[i].map((v) => v.toFixed(8))
      return [sid, cat, ...pcs].join(',')
    })
    downloadCsv(`pca_scores_${result.source_filename.replace('.csv', '')}.csv`, [header.join(','), ...rows].join('\n'))
  }

  const exportLoadings = () => {
    if (!result) return
    const header = ['PC', ...result.feature_columns]
    const rows = result.loadings.map((row, i) =>
      [`PC${i + 1}`, ...row.map((v) => v.toFixed(8))].join(',')
    )
    const evrLine = 'explained_variance_ratio,' + result.explained_variance_ratio.map((v) => v.toFixed(8)).join(',')
    const cumLine = 'cumulative_variance_ratio,' + result.cumulative_variance_ratio.map((v) => v.toFixed(8)).join(',')
    downloadCsv(
      `pca_loadings_${result.source_filename.replace('.csv', '')}.csv`,
      [header.join(','), ...rows, '', evrLine, cumLine].join('\n')
    )
  }

  /* ═════════════════════════════════════════════════════════════════
     Render
    ═════════════════════════════════════════════════════════════════ */
  return (
    <div className="flex flex-col gap-8">

      {/* Page header */}
      <div className="pb-6 border-b border-surface-border">
        <p className="eyebrow mb-3">
          <span className="w-5 h-px bg-text-muted inline-block" />
          Module 04
        </p>
        <h1 className="font-serif text-display-sm text-text-primary mb-2 leading-tight">
          PCA Analysis
        </h1>
        <p className="text-text-secondary text-sm leading-relaxed max-w-xl">
          Principal Component Analysis of measurement variables. sample_id and
          category columns are never included in the feature matrix — origin is used
          only for visualization colouring.
        </p>
      </div>

      {listLoading && (
        <div className="border border-surface-border bg-brand-white p-8 flex items-center justify-center gap-3">
          <SpinnerIcon className="w-5 h-5 animate-spin text-text-muted" />
          <p className="text-sm text-text-secondary">Loading datasets…</p>
        </div>
      )}

      {!listLoading && datasets.length > 0 && (
        <div className="grid lg:grid-cols-5 gap-6">

          {/* Left: config panel (3/5) */}
          <div className="lg:col-span-3 flex flex-col gap-5">

            {/* Input type selector */}
            <InputTypeSelector
              inputType={inputType}
              onInputType={(t) => { setInputType(t); setResult(null); setPhase('configuring') }}
              datasets={datasets}
              selectedRawId={selectedRawId}
              onSelectRaw={setSelectedRawId}
              processedList={processedList}
              selectedProcessedId={selectedProcessedId}
              onSelectProcessed={setSelectedProcessedId}
            />

            {/* Config panel */}
            {phase !== 'results' && detail && (
              <ConfigPanel
                sensorColumns={sensorColumns}
                selectedFeatures={selectedFeatures}
                columnUnits={columnUnits}
                categoryColumns={categoryColumns}
                nComponents={nComponents}
                maxComponents={maxComponents}
                experimentName={experimentName}
                inputType={inputType}
                processedDetail={processedDetail}
                onToggleFeature={toggleFeature}
                onToggleAll={toggleAll}
                onNComponents={setNComponents}
                onExperimentName={setExperimentName}
                onRun={() => handleRun(false)}
                onSave={() => handleRun(true)}
                running={running}
              />
            )}

            {/* Error */}
            {error && (
              <div className="flex items-start gap-2 px-4 py-3 bg-red-50 border border-red-200 rounded-sm">
                <WarnIcon className="w-4 h-4 text-red-500 shrink-0 mt-0.5" />
                <p className="text-sm text-red-700">{error}</p>
              </div>
            )}
          </div>

          {/* Right: experiment history (2/5) */}
          <div className="lg:col-span-2">
            <ExperimentHistory
              experiments={experiments}
              loading={historyLoading}
              deletingId={deletingId}
              onLoad={handleLoadExperiment}
              onDelete={handleDeleteExperiment}
              currentResult={result}
            />
          </div>
        </div>
      )}

      {/* Results dashboard */}
      {phase === 'results' && result && (
        <ResultsDashboard
          result={result}
          isLoadedExperiment={isLoadedExperiment}
          onExportScores={exportScores}
          onExportLoadings={exportLoadings}
          onReconfigure={() => { setResult(null); setIsLoadedExperiment(false); setPhase('configuring') }}
        />
      )}
    </div>
  )
}

/* ═════════════════════════════════════════════════════════════════
   InputTypeSelector
═════════════════════════════════════════════════════════════════ */
function InputTypeSelector({
  inputType, onInputType,
  datasets, selectedRawId, onSelectRaw,
  processedList, selectedProcessedId, onSelectProcessed,
}: {
  inputType:             InputType
  onInputType:           (t: InputType) => void
  datasets:              DatasetSummary[]
  selectedRawId:         string | null
  onSelectRaw:           (id: string) => void
  processedList:         ProcessedDatasetSummary[]
  selectedProcessedId:   string | null
  onSelectProcessed:     (id: string) => void
}) {
  return (
    <div className="border border-surface-border bg-brand-white">
      <div className="px-5 py-4 border-b border-surface-border">
        <h2 className="font-serif text-base text-text-primary">Select Input Data</h2>
      </div>
      <div className="p-5 flex flex-col gap-4">
        {/* Tabs */}
        <div className="flex gap-2">
          <TabBtn active={inputType === 'raw_dataset'} onClick={() => onInputType('raw_dataset')}>
            Raw Dataset
          </TabBtn>
          <TabBtn active={inputType === 'processed_dataset'} onClick={() => onInputType('processed_dataset')}>
            Processed Dataset
          </TabBtn>
        </div>

        {/* Raw dataset selector */}
        {inputType === 'raw_dataset' && (
          <select
            value={selectedRawId ?? ''}
            onChange={(e) => onSelectRaw(e.target.value)}
            className="w-full text-sm border border-surface-border bg-brand-white text-text-primary
                       rounded-sm px-3 py-2 focus:outline-none focus:border-forest-900/40 cursor-pointer"
          >
            {datasets.map((ds) => (
              <option key={ds.id} value={ds.id}>
                {ds.original_filename} — {ds.row_count} rows · {ds.sensor_column_count} variables
                {ds.measurement_type ? ` · ${MEASUREMENT_LABELS[ds.measurement_type] ?? ds.measurement_type}` : ''}
              </option>
            ))}
          </select>
        )}

        {/* Processed dataset selector */}
        {inputType === 'processed_dataset' && (
          <>
            <select
              value={selectedProcessedId ?? ''}
              onChange={(e) => onSelectProcessed(e.target.value)}
              className="w-full text-sm border border-surface-border bg-brand-white text-text-primary
                         rounded-sm px-3 py-2 focus:outline-none focus:border-forest-900/40 cursor-pointer"
            >
              {processedList.length === 0 ? (
                <option value="">No processed datasets available — run Preprocessing Studio first</option>
              ) : (
                processedList.map((p) => (
                  <option key={p.id} value={p.id}>
                    {prettyDatasetName(p.source_filename)} | {scalerLabel(p.scaler_type)} | {p.row_count} samples | {new Date(p.created_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })} | {new Date(p.created_at).toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', hour12: false })}
                  </option>
                ))
              )}
            </select>
            {processedList.length === 0 && (
              <p className="text-xs text-amber-700">
                Process this dataset in Preprocessing Studio to create a scaled input for PCA.
              </p>
            )}
          </>
        )}
      </div>
    </div>
  )
}

/* ═════════════════════════════════════════════════════════════════
   ConfigPanel
═════════════════════════════════════════════════════════════════ */
function ConfigPanel({
  sensorColumns, selectedFeatures, columnUnits, categoryColumns,
  nComponents, maxComponents, experimentName, inputType, processedDetail,
  onToggleFeature, onToggleAll, onNComponents, onExperimentName,
  onRun, onSave, running,
}: {
  sensorColumns:     string[]
  selectedFeatures:  string[]
  columnUnits:       Record<string, string>
  categoryColumns:   string[]
  nComponents:       number
  maxComponents:     number
  experimentName:     string
  inputType:         InputType
  processedDetail:   ProcessedDatasetDetail | null
  onToggleFeature:   (col: string) => void
  onToggleAll:       () => void
  onNComponents:     (n: number) => void
  onExperimentName:   (name: string) => void
  onRun:              () => void
  onSave:             () => void
  running:            boolean
}) {
  const allSelected = selectedFeatures.length === sensorColumns.length
  const canRun = selectedFeatures.length >= 2 && nComponents >= 2 && !running

  return (
    <div className="border border-surface-border bg-brand-white">
      <div className="px-5 py-4 border-b border-surface-border">
        <h3 className="font-serif text-base text-text-primary">PCA Configuration</h3>
      </div>

      <div className="p-5 flex flex-col gap-5">

        {/* Preprocessing info strip */}
        {inputType === 'raw_dataset' && (
          <div className="px-3 py-2 bg-surface-overlay/40 border border-surface-border rounded-sm text-xs text-text-secondary">
            <span className="text-text-muted">Note: </span>
            Raw dataset — PCA centres features but does not standardise their scales.
            For best results, use a processed (scaled) dataset.
          </div>
        )}
        {inputType === 'processed_dataset' && processedDetail && (
          <ProcessedConfigStrip detail={processedDetail} />
        )}

        {/* Feature selection */}
        <div>
          <div className="flex items-center justify-between mb-2">
            <p className="text-xs font-medium text-text-muted uppercase tracking-[0.1em]">
              Measurement Variables ({sensorColumns.length})
            </p>
            <button onClick={onToggleAll}
              className="text-xs text-text-muted hover:text-text-primary underline underline-offset-2">
              {allSelected ? 'Deselect all' : 'Select all'}
            </button>
          </div>
          <div className="flex flex-wrap gap-2">
            {sensorColumns.map((col) => {
              const checked = selectedFeatures.includes(col)
              const unit = columnUnits[col]
              return (
                <button key={col} onClick={() => onToggleFeature(col)}
                  className={[
                    'inline-flex items-center gap-1.5 px-3 py-1.5 rounded-sm border',
                    'text-xs font-mono transition-colors duration-150',
                    checked
                      ? 'bg-forest-900 text-brand-white border-forest-900'
                      : 'bg-brand-white text-text-secondary border-surface-border hover:border-forest-900/30',
                  ].join(' ')}>
                  {col}
                  {unit && (
                    <span className={`text-[9px] ${checked ? 'text-brand-white/70' : 'text-text-muted'}`}>{unit}</span>
                  )}
                </button>
              )
            })}
          </div>
          {categoryColumns.length > 0 && (
            <p className="text-xs text-text-muted mt-2">
              Category column(s) ({categoryColumns.join(', ')}) are used for visualization only
              and are never included in the feature matrix.
            </p>
          )}
        </div>

        {/* n_components */}
        <div>
          <label className="text-xs font-medium text-text-muted uppercase tracking-[0.1em] block mb-2">
            Number of Principal Components
          </label>
          <div className="flex items-center gap-3">
            <input
              type="range" min={2} max={maxComponents} step={1}
              value={Math.min(nComponents, maxComponents)}
              onChange={(e) => onNComponents(parseInt(e.target.value))}
              className="flex-1 accent-forest-900"
            />
            <input
              type="number" min={2} max={maxComponents}
              value={nComponents}
              onChange={(e) => onNComponents(Math.max(2, Math.min(maxComponents, parseInt(e.target.value) || 2)))}
              className="w-20 text-sm border border-surface-border rounded-sm px-3 py-1.5
                         bg-brand-white text-text-primary text-center font-mono
                         focus:outline-none focus:border-forest-900/40"
            />
            <span className="text-xs text-text-muted">max {maxComponents}</span>
          </div>
        </div>

        {/* Experiment name */}
        <div>
          <label className="text-xs font-medium text-text-muted uppercase tracking-[0.1em] block mb-2">
            Experiment Name (optional)
          </label>
          <input
            type="text"
            value={experimentName}
            onChange={(e) => onExperimentName(e.target.value)}
            placeholder="e.g. Magnolia E-Tongue — StandardScaler PCA"
            className="w-full text-sm border border-surface-border rounded-sm px-3 py-2
                       bg-brand-white text-text-primary placeholder:text-text-muted
                       focus:outline-none focus:border-forest-900/40"
          />
        </div>

        {/* Action buttons */}
        <div className="flex items-center gap-3 pt-2 border-t border-surface-border">
          <button
            onClick={onRun}
            disabled={!canRun}
            className="inline-flex items-center gap-2 px-5 py-2 text-sm font-medium
                       border border-forest-900 text-forest-900 rounded-sm
                       hover:bg-forest-900/[0.06] transition-colors duration-150
                       disabled:opacity-40 disabled:cursor-not-allowed"
          >
            {running ? <><SpinnerIcon className="w-4 h-4 animate-spin" />Running…</>
                     : <><ChartIcon className="w-4 h-4" />Run PCA</>}
          </button>
          <button
            onClick={onSave}
            disabled={!canRun}
            className="inline-flex items-center gap-2 px-5 py-2 text-sm font-medium
                       bg-forest-900 text-brand-white rounded-sm
                       hover:bg-forest-800 transition-colors duration-150
                       disabled:opacity-40 disabled:cursor-not-allowed"
          >
            {running ? <><SpinnerIcon className="w-4 h-4 animate-spin text-brand-white" />Saving…</>
                     : <><SaveIcon className="w-4 h-4" />Run & Save</>}
          </button>
          {selectedFeatures.length < 2 && (
            <p className="text-xs text-amber-700">Select at least 2 features.</p>
          )}
        </div>
      </div>
    </div>
  )
}

/* ═════════════════════════════════════════════════════════════════
   ProcessedConfigStrip — shows preprocessing pipeline config
═════════════════════════════════════════════════════════════════ */
function ProcessedConfigStrip({ detail }: { detail: ProcessedDatasetDetail }) {
  const config = (() => { try { return JSON.parse(detail.pipeline_config) } catch { return {} } })()
  const transforms: string[] = (() => {
    try { return JSON.parse(detail.transformations_applied) } catch { return [] }
  })()

  const scaling = config.scaling_method ?? 'none'
  const imputation = config.imputation_strategy ?? 'none'
  const outlier = config.outlier_action ?? 'keep'

  const parts: { label: string; value: string }[] = [
    { label: 'Scaling', value: scaling },
    { label: 'Imputation', value: imputation },
  ]
  if (outlier !== 'keep') {
    parts.push({ label: 'Outliers', value: `${outlier} (IQRx${config.iqr_multiplier ?? 1.5})` })
  }
  parts.push({ label: 'Features', value: String(detail.sensor_column_count) })

  return (
    <div className="px-3 py-2.5 bg-forest-900/[0.04] border border-forest-900/15 rounded-sm">
      <div className="flex items-center gap-1.5 mb-1.5">
        <span className="text-[10px] font-medium text-forest-900 uppercase tracking-[0.1em]">
          Preprocessing Applied
        </span>
      </div>
      <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs">
        {parts.map((p) => (
          <span key={p.label} className="text-text-secondary">
            <span className="text-text-muted">{p.label}: </span>
            <span className="font-mono">{p.value}</span>
          </span>
        ))}
        <span className="text-text-muted">
          <span className="text-text-muted">Created: </span>
          {new Date(detail.created_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}
        </span>
      </div>
      {transforms.length > 0 && (
        <div className="mt-1.5 flex flex-wrap gap-1">
          {transforms.map((t, i) => (
            <span key={i} className="text-[10px] text-text-muted">
              {i + 1}. {t}
            </span>
          ))}
        </div>
      )}
    </div>
  )
}

/* ═════════════════════════════════════════════════════════════════
   ResultsDashboard
═════════════════════════════════════════════════════════════════ */
function ResultsDashboard({
  result, isLoadedExperiment, onExportScores, onExportLoadings, onReconfigure,
}: {
  result:              PcaResult
  isLoadedExperiment:  boolean
  onExportScores: () => void
  onExportLoadings: () => void
  onReconfigure:  () => void
}) {
  return (
    <div className="flex flex-col gap-6">

      {/* Loaded experiment indicator */}
      {isLoadedExperiment && (
        <div className="flex items-center gap-2.5 px-4 py-2.5 bg-forest-900/[0.06] border border-forest-900/20 rounded-sm">
          <HistoryIcon className="w-4 h-4 text-forest-900 shrink-0" />
          <div className="flex flex-col min-w-0">
            <span className="text-xs font-medium text-forest-900">
              Loaded Experiment{result.experiment_name ? `: ${result.experiment_name}` : ''}
            </span>
            <span className="text-[11px] text-text-muted">
              Source: {result.source_filename} · {result.n_samples} samples · {result.n_features} variables
              {' · '}({result.input_type === 'raw_dataset' ? 'Raw' : 'Processed'} input)
            </span>
          </div>
        </div>
      )}

      {/* Summary header */}
      <div className="border border-surface-border bg-brand-white">
        <div className="px-6 py-5 border-b border-surface-border flex items-start justify-between gap-4 flex-wrap">
          <div>
            <h2 className="font-serif text-base text-text-primary mb-1">PCA Results</h2>
            <p className="text-xs text-text-muted">
              {result.source_filename} · {result.n_samples} samples · {result.n_features} measurement variables ·{' '}
              {result.n_components} components · sklearn {result.sklearn_version}
            </p>
            {result.preprocessing_summary && (
              <p className="text-xs text-text-secondary mt-1">
                {result.preprocessing_summary}
              </p>
            )}
            {result.experiment_name && (
              <p className="text-xs text-forest-900 font-medium mt-1">
                Experiment: {result.experiment_name}
              </p>
            )}
          </div>
          <div className="flex items-center gap-2">
            {result.experiment_id && (
              <span className="inline-flex items-center gap-1 px-2 py-0.5 text-[10px] font-medium
                               tracking-wide uppercase rounded-sm border
                               bg-forest-900/[0.07] text-forest-900 border-forest-900/20">
                Saved
              </span>
            )}
            <button onClick={onReconfigure}
              className="text-xs text-text-muted hover:text-text-primary underline underline-offset-2 transition-colors duration-150">
              Reconfigure
            </button>
          </div>
        </div>

        {/* Summary stats */}
        <div className="grid grid-cols-2 sm:grid-cols-4 divide-x divide-surface-border">
          <StatCell label="Samples" value={String(result.n_samples)} />
          <StatCell label="Variables" value={String(result.n_features)} />
          <StatCell label="Components" value={String(result.n_components)} />
          <StatCell label="Variance (PC1)" value={fmt(result.explained_variance_ratio[0] * 100, 2) + '%'} highlight />
        </div>
      </div>

      {/* Warnings */}
      {result.warnings.length > 0 && (
        <div className="flex flex-col gap-2">
          {result.warnings.map((w, i) => (
            <div key={i} className="flex items-start gap-2 px-4 py-3 bg-amber-50 border border-amber-200 rounded-sm">
              <WarnIcon className="w-4 h-4 text-amber-600 shrink-0 mt-0.5" />
              <p className="text-sm text-amber-800">{w}</p>
            </div>
          ))}
        </div>
      )}

      {/* Export buttons */}
      <div className="flex items-center gap-3 flex-wrap">
        <button onClick={onExportScores}
          className="inline-flex items-center gap-2 px-4 py-2 text-xs font-medium
                     border border-surface-border rounded-sm text-text-secondary
                     hover:text-text-primary hover:border-forest-900/30 transition-colors duration-150">
          <DownloadIcon className="w-3.5 h-3.5" /> Export Scores (CSV)
        </button>
        <button onClick={onExportLoadings}
          className="inline-flex items-center gap-2 px-4 py-2 text-xs font-medium
                     border border-surface-border rounded-sm text-text-secondary
                     hover:text-text-primary hover:border-forest-900/30 transition-colors duration-150">
          <DownloadIcon className="w-3.5 h-3.5" /> Export Loadings &amp; Variance (CSV)
        </button>
      </div>

      {/* Scree plot */}
      <ScreePlot result={result} />

      {/* Scatter plots */}
      {result.n_components >= 2 && (
        <ScatterPlot result={result} xComp={0} yComp={1} title="PC1 vs PC2" />
      )}
      {result.n_components >= 3 && (
        <ScatterPlot result={result} xComp={0} yComp={2} title="PC1 vs PC3" />
      )}
      {result.n_components >= 4 && (
        <ScatterPlot result={result} xComp={1} yComp={2} title="PC2 vs PC3" />
      )}

      {/* Loadings heatmap */}
      <LoadingsHeatmap result={result} />

      {/* Loading vectors table */}
      <LoadingsTable result={result} />

      {/* PC scores table */}
      <ScoresTable result={result} />
    </div>
  )
}

/* ═════════════════════════════════════════════════════════════════
   ScreePlot
═════════════════════════════════════════════════════════════════ */
function ScreePlot({ result }: { result: PcaResult }) {
  const { data, layout } = useMemo(() => {
    const labels = Array.from({ length: result.n_components }, (_, i) => `PC${i + 1}`)
    return {
      data: [
        {
          type: 'bar' as const,
          x: labels,
          y: result.explained_variance_ratio.map((v) => v * 100),
          name: 'Explained',
          marker: { color: '#32493F', line: { color: '#1C2A22', width: 0.5 } },
          yaxis: 'y',
        },
        {
          type: 'scatter' as const,
          mode: 'lines+markers' as const,
          x: labels,
          y: result.cumulative_variance_ratio.map((v) => v * 100),
          name: 'Cumulative',
          line: { color: '#C25E3A', width: 2 },
          marker: { color: '#C25E3A', size: 6 },
          yaxis: 'y2',
        },
      ],
      layout: {
        paper_bgcolor: 'rgba(0,0,0,0)',
        plot_bgcolor: 'rgba(0,0,0,0)',
        font: { family: 'Inter, system-ui, sans-serif', size: 11, color: '#4A5E50' },
        margin: { t: 10, r: 10, b: 44, l: 56 },
        legend: { x: 0.02, y: 0.98, font: { size: 10 }, bgcolor: 'rgba(0,0,0,0)' },
        xaxis: {
          gridcolor: '#D2DCDB', linecolor: '#D2DCDB', zerolinecolor: '#D2DCDB',
          tickcolor: '#D2DCDB', title: { text: 'Principal Component', font: { size: 11, color: '#1C2A22' } },
        },
        yaxis: {
          gridcolor: '#D2DCDB', linecolor: '#D2DCDB', zerolinecolor: '#D2DCDB',
          tickcolor: '#D2DCDB',
          title: { text: 'Explained Variance (%)', font: { size: 11, color: '#1C2A22' } },
          side: 'left',
          // Fix: use the same [0, 100] scale as yaxis2 so the cumulative
          // line and the individual bars share identical chart heights.
          // Without this, Plotly auto-ranges the left axis to ~[0, 65]
          // while yaxis2 is [0, 105], making the same percentage value
          // appear at ~85% height on the left vs ~52% on the right —
          // a 32-percentage-point visual offset (confirmed for E-Tongue).
          range: [0, 100],
        },
        yaxis2: {
          gridcolor: 'rgba(0,0,0,0)', overlaying: 'y', side: 'right',
          tickcolor: '#C25E3A', title: { text: 'Cumulative (%)', font: { size: 11, color: '#C25E3A' } },
          range: [0, 100],
        },
      },
    }
  }, [result])

  return (
    <div className="border border-surface-border bg-brand-white">
      <div className="px-6 py-4 border-b border-surface-border">
        <h3 className="font-serif text-base text-text-primary">Scree Plot — Explained Variance</h3>
        <p className="text-xs text-text-muted mt-0.5">
          Individual and cumulative explained variance per component.
        </p>
      </div>
      <div className="p-4">
        <PlotlyChart data={data} layout={layout} style={{ width: '100%', height: 320 }} />
      </div>
    </div>
  )
}

/* ═════════════════════════════════════════════════════════════════
   ScatterPlot
═════════════════════════════════════════════════════════════════ */
function ScatterPlot({ result, xComp, yComp, title }: {
  result: PcaResult
  xComp: number
  yComp: number
  title: string
}) {
  const hasCategory = result.category_labels.length > 0
  const uniqueLabels = useMemo(() => {
    if (!hasCategory) return []
    return [...new Set(result.category_labels)].sort()
  }, [hasCategory, result.category_labels])

  const { data, layout } = useMemo(() => {
    if (hasCategory && uniqueLabels.length > 0) {
      // One trace per category
      const traces = uniqueLabels.map((label, idx) => {
        const color = colorFor(label, idx)
        const mask = result.category_labels.map((l) => l === label)
        return {
          type: 'scatter' as const,
          mode: 'markers' as const,
          x: result.scores.filter((_, i) => mask[i]).map((row) => row[xComp]),
          y: result.scores.filter((_, i) => mask[i]).map((row) => row[yComp]),
          name: label,
          marker: {
            color,
            size: 10,
            line: { color: '#1C2A22', width: 0.5 },
            opacity: 0.85,
          },
          text: result.sample_ids.filter((_, i) => mask[i]),
          hovertemplate: '<b>%{text}</b><br>' +
            `PC${xComp + 1}: %{x:.4f}<br>PC${yComp + 1}: %{y:.4f}<br>` +
            `Origin: ${label}<extra></extra>`,
        }
      })
      return {
        data: traces,
        layout: scatterLayout(xComp, yComp, result.explained_variance_ratio),
      }
    } else {
      // Single trace, no category
      return {
        data: [{
          type: 'scatter' as const,
          mode: 'markers' as const,
          x: result.scores.map((row) => row[xComp]),
          y: result.scores.map((row) => row[yComp]),
          name: 'Samples',
          marker: { color: '#32493F', size: 10, line: { color: '#1C2A22', width: 0.5 }, opacity: 0.85 },
          text: result.sample_ids,
          hovertemplate: '<b>%{text}</b><br>' +
            `PC${xComp + 1}: %{x:.4f}<br>PC${yComp + 1}: %{y:.4f}<extra></extra>`,
        }],
        layout: scatterLayout(xComp, yComp, result.explained_variance_ratio),
      }
    }
  }, [result, xComp, yComp, hasCategory, uniqueLabels, title])

  return (
    <div className="border border-surface-border bg-brand-white">
      <div className="px-6 py-4 border-b border-surface-border flex items-center justify-between">
        <div>
          <h3 className="font-serif text-base text-text-primary">{title}</h3>
          <p className="text-xs text-text-muted mt-0.5">
            Sample scores coloured by {result.category_column || 'group'}.
            Hover to identify individual samples.
          </p>
        </div>
        <div className="text-xs text-text-muted font-mono">
          PC{xComp + 1}: {fmt(result.explained_variance_ratio[xComp] * 100, 2)}% ·{' '}
          PC{yComp + 1}: {fmt(result.explained_variance_ratio[yComp] * 100, 2)}%
        </div>
      </div>
      <div className="p-4">
        <PlotlyChart data={data} layout={layout} style={{ width: '100%', height: 400 }} />
      </div>
    </div>
  )
}

function scatterLayout(xComp: number, yComp: number, evr: number[]) {
  return {
    paper_bgcolor: 'rgba(0,0,0,0)',
    plot_bgcolor: 'rgba(0,0,0,0)',
    font: { family: 'Inter, system-ui, sans-serif', size: 11, color: '#4A5E50' },
    margin: { t: 10, r: 10, b: 48, l: 56 },
    legend: { x: 0.02, y: 0.98, font: { size: 10 }, bgcolor: 'rgba(255,255,255,0.8)' },
    xaxis: {
      gridcolor: '#D2DCDB', linecolor: '#D2DCDB', zerolinecolor: '#D2DCDB', zerolinewidth: 1,
      tickcolor: '#D2DCDB',
      title: { text: `PC${xComp + 1} (${(evr[xComp] * 100).toFixed(2)}%)`, font: { size: 11, color: '#1C2A22' } },
    },
    yaxis: {
      gridcolor: '#D2DCDB', linecolor: '#D2DCDB', zerolinecolor: '#D2DCDB', zerolinewidth: 1,
      tickcolor: '#D2DCDB',
      title: { text: `PC${yComp + 1} (${(evr[yComp] * 100).toFixed(2)}%)`, font: { size: 11, color: '#1C2A22' } },
    },
  }
}

/* ═════════════════════════════════════════════════════════════════
   LoadingsHeatmap
═════════════════════════════════════════════════════════════════ */
function LoadingsHeatmap({ result }: { result: PcaResult }) {
  const { data, layout } = useMemo(() => {
    const pcLabels = Array.from({ length: result.n_components }, (_, i) => `PC${i + 1}`)
    return {
      data: [{
        type: 'heatmap' as const,
        z: result.loadings,
        x: result.feature_columns,
        y: pcLabels,
        colorscale: [
          [0, '#C25E3A'], [0.5, '#F4F6F0'], [1, '#2D4A3E'],
        ] as any,
        zmid: 0,
        hovertemplate: '<b>%{y} × %{x}</b><br>Loading: %{z:.6f}<extra></extra>',
      }],
      layout: {
        paper_bgcolor: 'rgba(0,0,0,0)',
        plot_bgcolor: 'rgba(0,0,0,0)',
        font: { family: 'Inter, system-ui, sans-serif', size: 10, color: '#4A5E50' },
        margin: { t: 10, r: 10, b: 80, l: 56 },
        xaxis: {
          gridcolor: '#D2DCDB', linecolor: '#D2DCDB',
          tickangle: -45, tickfont: { size: 9 },
        },
        yaxis: {
          gridcolor: '#D2DCDB', linecolor: '#D2DCDB',
          tickfont: { size: 10 },
        },
      },
    }
  }, [result])

  return (
    <div className="border border-surface-border bg-brand-white">
      <div className="px-6 py-4 border-b border-surface-border">
        <h3 className="font-serif text-base text-text-primary">Loading Vectors — Feature Contributions</h3>
        <p className="text-xs text-text-muted mt-0.5">
          Each row is a principal component's loading vector (unit norm).
          Positive (dark green) and negative (terracotta) contributions show
          how each measurement variable influences each component.
        </p>
      </div>
      <div className="p-4">
        <PlotlyChart data={data} layout={layout} style={{ width: '100%', height: 320 }} />
      </div>
    </div>
  )
}

/* ═════════════════════════════════════════════════════════════════
   LoadingsTable
═════════════════════════════════════════════════════════════════ */
function LoadingsTable({ result }: { result: PcaResult }) {
  return (
    <div className="border border-surface-border bg-brand-white">
      <div className="px-6 py-4 border-b border-surface-border">
        <h3 className="font-serif text-base text-text-primary">Loading Vectors (Numerical)</h3>
        <p className="text-xs text-text-muted mt-0.5">
          Principal component loadings for each measurement variable.
        </p>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-xs border-collapse">
          <thead>
            <tr className="bg-surface-overlay border-b border-surface-border">
              <th className="px-4 py-2.5 text-left font-medium text-text-muted whitespace-nowrap sticky left-0 bg-surface-overlay">
                Variable
              </th>
              {Array.from({ length: result.n_components }, (_, i) => (
                <th key={i} className="px-4 py-2.5 text-right font-medium text-text-muted whitespace-nowrap">
                  PC{i + 1}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {result.feature_columns.map((col, fi) => (
              <tr key={col} className={`border-b border-surface-border last:border-0 ${fi % 2 === 0 ? 'bg-brand-white' : 'bg-surface-overlay/30'}`}>
                <td className="px-4 py-2.5 font-mono font-medium text-text-primary whitespace-nowrap sticky left-0
                               bg-brand-white">
                  {col}
                </td>
                {result.loadings.map((row, ci) => (
                  <td key={ci} className="px-4 py-2.5 text-right font-mono text-text-secondary">
                    {fmt(row[fi], 5)}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

/* ═════════════════════════════════════════════════════════════════
   ScoresTable
═════════════════════════════════════════════════════════════════ */
function ScoresTable({ result }: { result: PcaResult }) {
  const [page, setPage] = useState(1)
  const pageSize = 20
  const totalPages = Math.ceil(result.n_samples / pageSize)
  const start = (page - 1) * pageSize
  const end = Math.min(page * pageSize, result.n_samples)

  return (
    <div className="border border-surface-border bg-brand-white">
      <div className="px-6 py-4 border-b border-surface-border">
        <h3 className="font-serif text-base text-text-primary">PC Scores</h3>
        <p className="text-xs text-text-muted mt-0.5">
          Principal component scores for each sample. sample_id and origin are metadata only.
        </p>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-xs border-collapse">
          <thead>
            <tr className="bg-surface-overlay border-b border-surface-border">
              <th className="px-4 py-2.5 text-left font-medium text-text-muted whitespace-nowrap">#</th>
              <th className="px-4 py-2.5 text-left font-medium text-text-primary whitespace-nowrap">sample_id</th>
              {result.category_column && (
                <th className="px-4 py-2.5 text-left font-medium text-text-muted whitespace-nowrap">
                  {result.category_column}
                </th>
              )}
              {Array.from({ length: result.n_components }, (_, i) => (
                <th key={i} className="px-4 py-2.5 text-right font-medium text-forest-900 whitespace-nowrap">
                  PC{i + 1}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {result.sample_ids.slice(start, end).map((sid, si) => {
              const ri = start + si
              return (
                <tr key={sid} className={`border-b border-surface-border last:border-0 ${si % 2 === 0 ? 'bg-brand-white' : 'bg-surface-overlay/30'}`}>
                  <td className="px-4 py-2 text-right font-mono text-text-muted">{ri + 1}</td>
                  <td className="px-4 py-2 font-mono text-text-primary">{sid}</td>
                  {result.category_column && (
                    <td className="px-4 py-2 text-text-secondary">{result.category_labels[ri]}</td>
                  )}
                  {result.scores[ri].map((v, ci) => (
                    <td key={ci} className="px-4 py-2 text-right font-mono text-text-secondary">
                      {fmt(v, 5)}
                    </td>
                  ))}
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
      <div className="flex items-center justify-between px-4 py-3 border-t border-surface-border bg-surface-overlay/40">
        <p className="text-xs text-text-muted">Rows {start + 1}–{end} of {result.n_samples}</p>
        <div className="flex items-center gap-1">
          <PageBtn label="‹ Prev" disabled={page <= 1} onClick={() => setPage(page - 1)} />
          <span className="px-3 py-1 text-xs text-text-muted">{page} / {totalPages}</span>
          <PageBtn label="Next ›" disabled={page >= totalPages} onClick={() => setPage(page + 1)} />
        </div>
      </div>
    </div>
  )
}

/* ═════════════════════════════════════════════════════════════════
   ExperimentHistory
═════════════════════════════════════════════════════════════════ */
function ExperimentHistory({
  experiments, loading, deletingId, onLoad, onDelete, currentResult,
}: {
  experiments:   PcaExperimentSummary[]
  loading:       boolean
  deletingId:     string | null
  onLoad:        (id: string) => void
  onDelete:      (id: string) => void
  currentResult: PcaResult | null
}) {
  return (
    <div className="border border-surface-border bg-brand-white">
      <div className="px-5 py-4 border-b border-surface-border flex items-center justify-between">
        <h2 className="font-serif text-base text-text-primary">Experiments</h2>
        {!loading && <span className="text-xs text-text-muted font-mono">{experiments.length}</span>}
      </div>

      {loading && (
        <div className="p-6 flex justify-center">
          <SpinnerIcon className="w-5 h-5 animate-spin text-text-muted" />
        </div>
      )}

      {!loading && experiments.length === 0 && (
        <div className="p-6 text-center">
          <p className="text-xs text-text-muted">No saved experiments yet.</p>
          <p className="text-xs text-text-muted mt-1">Run &amp; Save to store results here.</p>
        </div>
      )}

      {!loading && experiments.length > 0 && (
        <ul className="divide-y divide-surface-border max-h-[600px] overflow-y-auto">
          {experiments.map((exp) => {
            const isActive = currentResult?.experiment_id === exp.id
            const evr: number[] = (() => { try { return JSON.parse(exp.explained_variance_ratio) } catch { return [] } })()
            return (
              <li key={exp.id}
                onClick={() => onLoad(exp.id)}
                className={['px-5 py-4 cursor-pointer group transition-colors duration-150',
                  isActive ? 'bg-sage-100/60' : 'hover:bg-surface-overlay/50'].join(' ')}>
                <div className="flex items-start justify-between gap-2">
                  <div className="min-w-0 flex-1">
                    <p className="text-xs font-medium text-text-primary truncate">
                      {exp.experiment_name || exp.source_filename}
                    </p>
                    <p className="text-[10px] text-text-muted mt-0.5">
                      {exp.n_components} PCs · {exp.n_features} vars · {' '}
                      {evr.length > 0 ? `${(evr[0] * 100).toFixed(1)}%` : '?'} PC1
                    </p>
                    <p className="text-[10px] text-text-muted mt-0.5">
                      {exp.input_type === 'raw_dataset' ? 'Raw' : 'Processed'} · {' '}
                      {new Date(exp.created_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}
                    </p>
                  </div>
                  <button
                    onClick={(e) => { e.stopPropagation(); onDelete(exp.id) }}
                    disabled={deletingId === exp.id}
                    className="shrink-0 text-text-muted hover:text-red-600
                               opacity-0 group-hover:opacity-100 transition-all duration-150 p-1"
                    aria-label="Delete experiment"
                  >
                    {deletingId === exp.id
                      ? <SpinnerIcon className="w-3.5 h-3.5 animate-spin" />
                      : <TrashIcon className="w-3.5 h-3.5" />}
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

/* ═════════════════════════════════════════════════════════════════
   Small reusable components
═════════════════════════════════════════════════════════════════ */
function TabBtn({ active, onClick, children }: { active: boolean; onClick: () => void; children: React.ReactNode }) {
  return (
    <button onClick={onClick}
      className={[
        'px-4 py-2 text-xs font-medium rounded-sm border transition-colors duration-150',
        active
          ? 'bg-forest-900 text-brand-white border-forest-900'
          : 'bg-brand-white text-text-secondary border-surface-border hover:border-forest-900/30',
      ].join(' ')}>
      {children}
    </button>
  )
}

function StatCell({ label, value, highlight = false }: { label: string; value: string; highlight?: boolean }) {
  return (
    <div className="px-6 py-4">
      <p className="text-xs text-text-muted mb-1">{label}</p>
      <p className={`text-sm font-medium font-mono ${highlight ? 'text-forest-900' : 'text-text-primary'}`}>{value}</p>
    </div>
  )
}

function PageBtn({ label, onClick, disabled }: { label: string; onClick: () => void; disabled: boolean }) {
  return (
    <button onClick={onClick} disabled={disabled}
      className={['px-3 py-1 text-xs border border-surface-border rounded-sm transition-colors duration-150',
        disabled ? 'text-text-muted cursor-not-allowed' : 'text-text-primary hover:bg-surface-overlay cursor-pointer'].join(' ')}>
      {label}
    </button>
  )
}

/* ═════════════════════════════════════════════════════════════════
   Constants
═════════════════════════════════════════════════════════════════ */
const MEASUREMENT_LABELS: Record<string, string> = {
  electronic_tongue:  'Electronic Tongue',
  electronic_nose:    'Electronic Nose',
  chemical_analysis:  'Chemical Analysis',
}

/* ═════════════════════════════════════════════════════════════════
   Icons
═════════════════════════════════════════════════════════════════ */
function SpinnerIcon({ className = '' }: { className?: string }) {
  return (
    <svg className={className} xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" aria-hidden="true">
      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
    </svg>
  )
}

function ChartIcon({ className = '' }: { className?: string }) {
  return (
    <svg viewBox="0 0 16 16" fill="none" className={className} xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
      <path d="M2 2v12h12" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" />
      <circle cx="5" cy="10" r="1.5" stroke="currentColor" strokeWidth="1.3" />
      <circle cx="8" cy="6" r="1.5" stroke="currentColor" strokeWidth="1.3" />
      <circle cx="11" cy="8" r="1.5" stroke="currentColor" strokeWidth="1.3" />
    </svg>
  )
}

function SaveIcon({ className = '' }: { className?: string }) {
  return (
    <svg viewBox="0 0 16 16" fill="none" className={className} xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
      <rect x="2" y="2" width="12" height="12" rx="1" stroke="currentColor" strokeWidth="1.3" />
      <path d="M5 2v4h6V2M8 9v4" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" />
    </svg>
  )
}

function WarnIcon({ className = '' }: { className?: string }) {
  return (
    <svg viewBox="0 0 16 16" fill="none" className={className} xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
      <path d="M8 2L14.5 13.5H1.5L8 2Z" stroke="currentColor" strokeWidth="1.3" strokeLinejoin="round" />
      <path d="M8 6.5v3M8 11v.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
    </svg>
  )
}

function TrashIcon({ className = '' }: { className?: string }) {
  return (
    <svg viewBox="0 0 16 16" fill="none" className={className} xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
      <path d="M3 4h10M6 4V2.5a.5.5 0 01.5-.5h3a.5.5 0 01.5.5V4M5 4l.5 9h5l.5-9"
        stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  )
}

function HistoryIcon({ className = '' }: { className?: string }) {
  return (
    <svg viewBox="0 0 16 16" fill="none" className={className} xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
      <path d="M2.5 8a5.5 5.5 0 1 0 1.7-3.94M2.5 3v2.5H5"
        stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" strokeLinejoin="round" />
      <path d="M8 5v3l2 1.5" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  )
}

function DownloadIcon({ className = '' }: { className?: string }) {
  return (
    <svg viewBox="0 0 16 16" fill="none" className={className} xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
      <path d="M8 2v8M5 7l3 3 3-3M2 13h12" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  )
}
