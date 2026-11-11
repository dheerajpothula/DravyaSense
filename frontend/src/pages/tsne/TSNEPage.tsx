import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
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
  type TsneExperimentSummary,
  type TsneResult,
  type TsneRunRequest,
  ApiError as TsneApiError,
  deleteTsneExperiment,
  getTsneExperiment,
  listTsneExperiments,
  runTsne,
  saveTsne,
} from '../../api/tsne'
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
   Category colour palette — matches PCA module
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
   Constants
───────────────────────────────────────────────────────────────── */
const MEASUREMENT_LABELS: Record<string, string> = {
  electronic_tongue:  'Electronic Tongue',
  electronic_nose:    'Electronic Nose',
  chemical_analysis:  'Chemical Analysis',
}

// Default t-SNE hyperparameters
const DEFAULT_PERPLEXITY         = 30
const DEFAULT_LEARNING_RATE_MODE = 'auto' as const
const DEFAULT_LEARNING_RATE      = 200
const DEFAULT_MAX_ITER           = 1000
const DEFAULT_RANDOM_STATE       = 42
const DEFAULT_METRIC             = 'euclidean'
const DEFAULT_INIT               = 'pca' as const

/* ─────────────────────────────────────────────────────────────────
   Phase
───────────────────────────────────────────────────────────────── */
type Phase = 'idle' | 'configuring' | 'running' | 'results' | 'error'
type LearningRateMode = 'auto' | 'manual'

/* ═════════════════════════════════════════════════════════════════
   Main Page Component
═════════════════════════════════════════════════════════════════ */
export default function TSNEPage() {
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

  // ── Feature selection ─────────────────────────────────────────
  const [selectedFeatures, setSelectedFeatures] = useState<string[]>([])

  // ── t-SNE hyperparameters ─────────────────────────────────────
  const [nComponents, setNComponents]           = useState<2 | 3>(2)
  const [perplexity, setPerplexity]             = useState(DEFAULT_PERPLEXITY)
  const [lrMode, setLrMode]                     = useState<LearningRateMode>(DEFAULT_LEARNING_RATE_MODE)
  const [learningRate, setLearningRate]         = useState(DEFAULT_LEARNING_RATE)
  const [maxIter, setMaxIter]                   = useState(DEFAULT_MAX_ITER)
  const [randomState, setRandomState]           = useState(DEFAULT_RANDOM_STATE)
  const [metric, setMetric]                     = useState(DEFAULT_METRIC)
  const [initMethod, setInitMethod]             = useState<'pca' | 'random'>(DEFAULT_INIT)
  const [experimentName, setExperimentName]     = useState('')

  // ── Results ───────────────────────────────────────────────────
  const [result, setResult]                     = useState<TsneResult | null>(null)
  const [running, setRunning]                   = useState(false)
  const [error, setError]                       = useState<string | null>(null)
  const [isLoadedExperiment, setIsLoadedExperiment] = useState(false)

  // ── Experiment history ────────────────────────────────────────
  const [experiments, setExperiments]           = useState<TsneExperimentSummary[]>([])
  const [historyLoading, setHistoryLoading]     = useState(false)
  const [deletingId, setDeletingId]             = useState<string | null>(null)

  // ── Phase ─────────────────────────────────────────────────────
  const [phase, setPhase] = useState<Phase>('idle')

  // ── Scroll target for results section ────────────────────────
  const resultsSectionRef = useRef<HTMLDivElement>(null)
  // Set to true by handleRun/handleLoadExperiment immediately before
  // setPhase('results') so the post-render effect can consume it once.
  const pendingScrollRef = useRef(false)

  /* ── Smooth-scroll to results top after a run or load ───────── */
  useEffect(() => {
    // Only scroll when a run/load explicitly requested it.
    if (!pendingScrollRef.current) return
    pendingScrollRef.current = false

    const el = resultsSectionRef.current
    if (!el) return

    // The Dashboard scroll container is <main class="overflow-y-auto">.
    // scrollIntoView scrolls the nearest scrollable ancestor — that is
    // <main>, not window — so this correctly positions the results heading
    // near the top of the visible content area without touching window.
    el.scrollIntoView({ behavior: 'smooth', block: 'start' })
  })

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

  // Max valid perplexity = n_samples - 1
  const maxPerplexity = useMemo(() => {
    if (!detail) return 59
    return Math.max(1, detail.row_count - 1)
  }, [detail])

  /* ── Load dataset list ──────────────────────────────────────── */
  useEffect(() => {
    listDatasets()
      .then((list) => {
        setDatasets(list)
        setListLoading(false)
        // Prefer Magnolia Electronic Tongue — same logic as PCA module
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
        // Clamp perplexity to valid range for new dataset
        setPerplexity((prev) => Math.min(prev, Math.max(1, d.row_count - 1)))
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
          getDataset(selectedRawId)
            .then((d) => {
              setDetail(d)
              const roles: Record<string, string> = JSON.parse(d.column_roles || '{}')
              const sensors = Object.entries(roles).filter(([, r]) => r === 'sensor').map(([c]) => c)
              const procFeats: string[] = (() => {
                try { return JSON.parse(list[0].selected_features) } catch { return sensors }
              })()
              setSelectedFeatures(procFeats)
              setPerplexity((prev) => Math.min(prev, Math.max(1, d.row_count - 1)))
              setPhase('configuring')
            })
            .catch(() => { setPhase('error') })
        } else {
          setPhase('idle')
        }
      })
      .catch(() => {})
  }, [inputType, selectedRawId])

  /* ── Update features when processed selection changes ───────── */
  useEffect(() => {
    if (inputType !== 'processed_dataset' || !selectedProcessedId || processedList.length === 0) return
    const proc = processedList.find((p) => p.id === selectedProcessedId)
    if (!proc) return
    const feats: string[] = (() => { try { return JSON.parse(proc.selected_features) } catch { return [] } })()
    setSelectedFeatures(feats)
    setPerplexity((prev) => Math.min(prev, Math.max(1, proc.row_count - 1)))
    getProcessedDetail(selectedProcessedId)
      .then((d) => setProcessedDetail(d))
      .catch(() => setProcessedDetail(null))
  }, [selectedProcessedId, processedList, inputType])

  /* ── Load experiment history ────────────────────────────────── */
  const refreshHistory = useCallback(async () => {
    setHistoryLoading(true)
    try {
      const list = await listTsneExperiments()
      setExperiments(list)
    } catch { /* silent */ } finally {
      setHistoryLoading(false)
    }
  }, [])

  useEffect(() => { refreshHistory() }, [refreshHistory])

  /* ── Run t-SNE ──────────────────────────────────────────────── */
  const handleRun = useCallback(async (save: boolean) => {
    const inputId = inputType === 'raw_dataset' ? selectedRawId : selectedProcessedId
    if (!inputId) return
    setRunning(true)
    setError(null)
    setPhase('running')
    setIsLoadedExperiment(false)

    const req: TsneRunRequest = {
      input_type:         inputType,
      input_id:           inputId,
      n_components:       nComponents,
      perplexity,
      learning_rate:      lrMode === 'auto' ? 'auto' : learningRate,
      early_exaggeration: 12.0,
      max_iter:           maxIter,
      random_state:       randomState,
      metric,
      init:               initMethod,
      feature_columns:    selectedFeatures.length > 0 ? selectedFeatures : null,
      experiment_name:    save ? (experimentName.trim() || null) : null,
    }

    try {
      const r = save ? await saveTsne(req) : await runTsne(req)
      setResult(r)
      pendingScrollRef.current = true
      setPhase('results')
      if (save) refreshHistory()
    } catch (err) {
      const msg = err instanceof TsneApiError ? err.message : 't-SNE computation failed.'
      setError(msg)
      setPhase('error')
    } finally {
      setRunning(false)
    }
  }, [
    inputType, selectedRawId, selectedProcessedId,
    nComponents, perplexity, lrMode, learningRate,
    maxIter, randomState, metric, initMethod,
    selectedFeatures, experimentName, refreshHistory,
  ])

  /* ── Load saved experiment ──────────────────────────────────── */
  const handleLoadExperiment = useCallback(async (id: string) => {
    setRunning(true)
    setError(null)
    try {
      const r = await getTsneExperiment(id)
      setResult(r)
      pendingScrollRef.current = true
      setPhase('results')
      setIsLoadedExperiment(true)

      // Restore original configuration so Reconfigure returns to the
      // exact settings that produced this experiment.
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
      setNComponents(r.n_components === 3 ? 3 : 2)
      setPerplexity(r.perplexity)
      setLrMode('manual')
      setLearningRate(r.learning_rate)
      setMaxIter(r.max_iter)
      setRandomState(r.random_state)
      setMetric(r.metric)
      setInitMethod(r.init === 'random' ? 'random' : 'pca')
      if (r.experiment_name) setExperimentName(r.experiment_name)
    } catch (err) {
      setError(err instanceof TsneApiError ? err.message : 'Could not load experiment.')
      setPhase('error')
    } finally {
      setRunning(false)
    }
  }, [])

  /* ── Delete experiment ──────────────────────────────────────── */
  const handleDeleteExperiment = useCallback(async (id: string) => {
    setDeletingId(id)
    try {
      await deleteTsneExperiment(id)
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
  const exportEmbedding = () => {
    if (!result) return
    const dimLabels = Array.from({ length: result.n_components }, (_, i) => `tsne_${i + 1}`)
    const header = ['sample_id', 'category', ...dimLabels]
    const rows = result.sample_ids.map((sid, i) => {
      const cat  = result.category_labels[i] || ''
      const dims = result.embedding[i].map((v) => v.toFixed(8))
      return [sid, cat, ...dims].join(',')
    })
    downloadCsv(
      `tsne_embedding_${result.source_filename.replace('.csv', '')}.csv`,
      [header.join(','), ...rows].join('\n')
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
          Module 05
        </p>
        <h1 className="font-serif text-display-sm text-text-primary mb-2 leading-tight">
          t-SNE Analysis
        </h1>
        <p className="text-text-secondary text-sm leading-relaxed max-w-xl">
          t-Distributed Stochastic Neighbour Embedding of measurement variables.
          sample_id and category columns are never included in the embedding —
          origin is used only for visualisation colouring.
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
                perplexity={perplexity}
                maxPerplexity={maxPerplexity}
                lrMode={lrMode}
                learningRate={learningRate}
                maxIter={maxIter}
                randomState={randomState}
                metric={metric}
                initMethod={initMethod}
                experimentName={experimentName}
                inputType={inputType}
                processedDetail={processedDetail}
                onToggleFeature={toggleFeature}
                onToggleAll={toggleAll}
                onNComponents={setNComponents}
                onPerplexity={setPerplexity}
                onLrMode={setLrMode}
                onLearningRate={setLearningRate}
                onMaxIter={setMaxIter}
                onRandomState={setRandomState}
                onMetric={setMetric}
                onInitMethod={setInitMethod}
                onExperimentName={setExperimentName}
                onRun={() => handleRun(false)}
                onSave={() => handleRun(true)}
                running={running}
              />
            )}

            {/* Error banner */}
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
        <div ref={resultsSectionRef}>
          <ResultsDashboard
            result={result}
            isLoadedExperiment={isLoadedExperiment}
            onExport={exportEmbedding}
            onReconfigure={() => {
              setResult(null)
              setIsLoadedExperiment(false)
              setPhase('configuring')
            }}
          />
        </div>
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
        <div className="flex gap-2">
          <TabBtn active={inputType === 'raw_dataset'}       onClick={() => onInputType('raw_dataset')}>Raw Dataset</TabBtn>
          <TabBtn active={inputType === 'processed_dataset'} onClick={() => onInputType('processed_dataset')}>Processed Dataset</TabBtn>
        </div>

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
                Process this dataset in Preprocessing Studio to create a scaled input for t-SNE.
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
  nComponents, perplexity, maxPerplexity, lrMode, learningRate,
  maxIter, randomState, metric, initMethod,
  experimentName, inputType, processedDetail,
  onToggleFeature, onToggleAll, onNComponents, onPerplexity,
  onLrMode, onLearningRate, onMaxIter, onRandomState,
  onMetric, onInitMethod, onExperimentName,
  onRun, onSave, running,
}: {
  sensorColumns:    string[]
  selectedFeatures: string[]
  columnUnits:      Record<string, string>
  categoryColumns:  string[]
  nComponents:      2 | 3
  perplexity:       number
  maxPerplexity:    number
  lrMode:           LearningRateMode
  learningRate:     number
  maxIter:          number
  randomState:      number
  metric:           string
  initMethod:       'pca' | 'random'
  experimentName:   string
  inputType:        InputType
  processedDetail:  ProcessedDatasetDetail | null
  onToggleFeature:  (col: string) => void
  onToggleAll:      () => void
  onNComponents:    (n: 2 | 3) => void
  onPerplexity:     (v: number) => void
  onLrMode:         (m: LearningRateMode) => void
  onLearningRate:   (v: number) => void
  onMaxIter:        (v: number) => void
  onRandomState:    (v: number) => void
  onMetric:         (v: string) => void
  onInitMethod:     (v: 'pca' | 'random') => void
  onExperimentName: (v: string) => void
  onRun:            () => void
  onSave:           () => void
  running:          boolean
}) {
  const allSelected = selectedFeatures.length === sensorColumns.length
  const canRun = selectedFeatures.length >= 2 && !running

  return (
    <div className="border border-surface-border bg-brand-white">
      <div className="px-5 py-4 border-b border-surface-border">
        <h3 className="font-serif text-base text-text-primary">t-SNE Configuration</h3>
      </div>

      <div className="p-5 flex flex-col gap-5">

        {/* Preprocessing info strip */}
        {inputType === 'raw_dataset' && (
          <div className="px-3 py-2 bg-surface-overlay/40 border border-surface-border rounded-sm text-xs text-text-secondary">
            <span className="text-text-muted">Note: </span>
            Raw dataset — features are not scaled. For best results, use a processed (scaled) dataset.
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
              Category column(s) ({categoryColumns.join(', ')}) are used for visualisation only
              and are never included in the feature matrix.
            </p>
          )}
        </div>

        {/* Embedding dimensions */}
        <div>
          <p className="text-xs font-medium text-text-muted uppercase tracking-[0.1em] mb-2">
            Embedding Dimensions
          </p>
          <div className="flex gap-2">
            <TabBtn active={nComponents === 2} onClick={() => onNComponents(2)}>2D</TabBtn>
            <TabBtn active={nComponents === 3} onClick={() => onNComponents(3)}>3D</TabBtn>
          </div>
        </div>

        {/* Perplexity */}
        <div>
          <label className="text-xs font-medium text-text-muted uppercase tracking-[0.1em] block mb-2">
            Perplexity
            <span className="normal-case font-normal ml-1 text-text-muted">(must be &lt; {maxPerplexity + 1} samples)</span>
          </label>
          <div className="flex items-center gap-3">
            <input
              type="range" min={1} max={maxPerplexity} step={1}
              value={Math.min(perplexity, maxPerplexity)}
              onChange={(e) => onPerplexity(parseInt(e.target.value))}
              className="flex-1 accent-forest-900"
            />
            <input
              type="number" min={1} max={maxPerplexity}
              value={perplexity}
              onChange={(e) => {
                const v = parseInt(e.target.value) || 1
                onPerplexity(Math.max(1, Math.min(maxPerplexity, v)))
              }}
              className="w-20 text-sm border border-surface-border rounded-sm px-3 py-1.5
                         bg-brand-white text-text-primary text-center font-mono
                         focus:outline-none focus:border-forest-900/40"
            />
            <span className="text-xs text-text-muted">max {maxPerplexity}</span>
          </div>
          <p className="text-[11px] text-text-muted mt-1">
            Typical range: 5–50. Controls effective neighbourhood size.
          </p>
        </div>

        {/* Learning rate */}
        <div>
          <p className="text-xs font-medium text-text-muted uppercase tracking-[0.1em] mb-2">
            Learning Rate
          </p>
          <div className="flex gap-2 mb-2">
            <TabBtn active={lrMode === 'auto'}   onClick={() => onLrMode('auto')}>Auto</TabBtn>
            <TabBtn active={lrMode === 'manual'} onClick={() => onLrMode('manual')}>Manual</TabBtn>
          </div>
          {lrMode === 'auto' ? (
            <p className="text-xs text-text-muted">
              Resolved as max(n_samples / 48, 50). Reported in results.
            </p>
          ) : (
            <input
              type="number" min={10} max={1000} step={10}
              value={learningRate}
              onChange={(e) => onLearningRate(Math.max(10, parseInt(e.target.value) || 200))}
              className="w-28 text-sm border border-surface-border rounded-sm px-3 py-1.5
                         bg-brand-white text-text-primary text-center font-mono
                         focus:outline-none focus:border-forest-900/40"
            />
          )}
        </div>

        {/* Iterations */}
        <div>
          <label className="text-xs font-medium text-text-muted uppercase tracking-[0.1em] block mb-2">
            Max Iterations
          </label>
          <div className="flex items-center gap-3">
            <input
              type="range" min={250} max={2000} step={50}
              value={maxIter}
              onChange={(e) => onMaxIter(parseInt(e.target.value))}
              className="flex-1 accent-forest-900"
            />
            <input
              type="number" min={250} max={2000}
              value={maxIter}
              onChange={(e) => onMaxIter(Math.max(250, Math.min(2000, parseInt(e.target.value) || 1000)))}
              className="w-20 text-sm border border-surface-border rounded-sm px-3 py-1.5
                         bg-brand-white text-text-primary text-center font-mono
                         focus:outline-none focus:border-forest-900/40"
            />
          </div>
        </div>

        {/* Advanced: seed / metric / init — collapsed into a tidy row */}
        <div className="grid grid-cols-3 gap-3">
          <div>
            <label className="text-xs font-medium text-text-muted uppercase tracking-[0.1em] block mb-1.5">
              Random Seed
            </label>
            <input
              type="number" min={0}
              value={randomState}
              onChange={(e) => onRandomState(Math.max(0, parseInt(e.target.value) || 0))}
              className="w-full text-sm border border-surface-border rounded-sm px-3 py-1.5
                         bg-brand-white text-text-primary text-center font-mono
                         focus:outline-none focus:border-forest-900/40"
            />
          </div>
          <div>
            <label className="text-xs font-medium text-text-muted uppercase tracking-[0.1em] block mb-1.5">
              Metric
            </label>
            <select
              value={metric}
              onChange={(e) => onMetric(e.target.value)}
              className="w-full text-sm border border-surface-border bg-brand-white text-text-primary
                         rounded-sm px-2 py-1.5 focus:outline-none focus:border-forest-900/40 cursor-pointer"
            >
              <option value="euclidean">Euclidean</option>
              <option value="cosine">Cosine</option>
              <option value="manhattan">Manhattan</option>
              <option value="correlation">Correlation</option>
            </select>
          </div>
          <div>
            <label className="text-xs font-medium text-text-muted uppercase tracking-[0.1em] block mb-1.5">
              Init
            </label>
            <select
              value={initMethod}
              onChange={(e) => onInitMethod(e.target.value as 'pca' | 'random')}
              className="w-full text-sm border border-surface-border bg-brand-white text-text-primary
                         rounded-sm px-2 py-1.5 focus:outline-none focus:border-forest-900/40 cursor-pointer"
            >
              <option value="pca">PCA (recommended)</option>
              <option value="random">Random</option>
            </select>
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
            placeholder="e.g. Magnolia E-Tongue — StandardScaler t-SNE p30"
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
            {running
              ? <><SpinnerIcon className="w-4 h-4 animate-spin" />Running…</>
              : <><ScatterIcon className="w-4 h-4" />Run t-SNE</>}
          </button>
          <button
            onClick={onSave}
            disabled={!canRun}
            className="inline-flex items-center gap-2 px-5 py-2 text-sm font-medium
                       bg-forest-900 text-brand-white rounded-sm
                       hover:bg-forest-800 transition-colors duration-150
                       disabled:opacity-40 disabled:cursor-not-allowed"
          >
            {running
              ? <><SpinnerIcon className="w-4 h-4 animate-spin text-brand-white" />Saving…</>
              : <><SaveIcon className="w-4 h-4" />Run &amp; Save</>}
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
  const scaling    = config.scaling_method    ?? 'none'
  const imputation = config.imputation_strategy ?? 'none'
  const outlier    = config.outlier_action    ?? 'keep'

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
            <span key={i} className="text-[10px] text-text-muted">{i + 1}. {t}</span>
          ))}
        </div>
      )}
    </div>
  )
}

/* ═════════════════════════════════════════════════════════════════
   ExperimentHistory
═════════════════════════════════════════════════════════════════ */
function ExperimentHistory({
  experiments, loading, deletingId, onLoad, onDelete, currentResult,
}: {
  experiments:   TsneExperimentSummary[]
  loading:       boolean
  deletingId:    string | null
  onLoad:        (id: string) => void
  onDelete:      (id: string) => void
  currentResult: TsneResult | null
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
                      {exp.n_components}D · {exp.n_features} vars · p={exp.perplexity}
                    </p>
                    <p className="text-[10px] text-text-muted mt-0.5">
                      {exp.input_type === 'raw_dataset' ? 'Raw' : 'Processed'} · seed={exp.random_state} ·{' '}
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
   ResultsDashboard
═════════════════════════════════════════════════════════════════ */
function ResultsDashboard({
  result, isLoadedExperiment, onExport, onReconfigure,
}: {
  result:              TsneResult
  isLoadedExperiment:  boolean
  onExport:            () => void
  onReconfigure:       () => void
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

      {/* t-SNE interpretation note */}
      <div className="flex items-start gap-2.5 px-4 py-3 bg-amber-50 border border-amber-200/60 rounded-sm">
        <InfoIcon className="w-4 h-4 text-amber-700 shrink-0 mt-0.5" />
        <p className="text-xs text-amber-800 leading-relaxed">
          <span className="font-medium">Interpretation: </span>
          t-SNE preserves <span className="font-medium">local neighbourhood structure</span>.
          Points that appear close in this embedding were close in the original feature space.
          However, the distances <span className="font-medium">between clusters</span> are{' '}
          <span className="font-medium">not directly interpretable</span> — they depend on perplexity
          and the stochastic optimisation, not on absolute inter-group distances.
          Do not use this plot alone to claim statistically significant category separation.
        </p>
      </div>

      {/* Summary header */}
      <div className="border border-surface-border bg-brand-white">
        <div className="px-6 py-5 border-b border-surface-border flex items-start justify-between gap-4 flex-wrap">
          <div>
            <h2 className="font-serif text-base text-text-primary mb-1">t-SNE Results</h2>
            <p className="text-xs text-text-muted">
              {result.source_filename} · {result.n_samples} samples · {result.n_features} measurement variables ·{' '}
              {result.n_components}D embedding · sklearn {result.sklearn_version}
            </p>
            {result.preprocessing_summary && (
              <p className="text-xs text-text-secondary mt-1">{result.preprocessing_summary}</p>
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

        {/* Parameter summary grid */}
        <div className="grid grid-cols-2 sm:grid-cols-4 divide-x divide-surface-border border-b border-surface-border">
          <StatCell label="Samples"    value={String(result.n_samples)} />
          <StatCell label="Variables"  value={String(result.n_features)} />
          <StatCell label="Dimensions" value={`${result.n_components}D`} />
          <StatCell label="Perplexity" value={String(result.perplexity)} highlight />
        </div>
        <div className="grid grid-cols-2 sm:grid-cols-4 divide-x divide-surface-border">
          <StatCell label="Learning Rate" value={fmt(result.learning_rate, 2)} />
          <StatCell label="Max Iterations" value={String(result.max_iter)} />
          <StatCell label="Random Seed"   value={String(result.random_state)} />
          <StatCell label="Init"          value={result.init} />
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

      {/* Export */}
      <div className="flex items-center gap-3 flex-wrap">
        <button onClick={onExport}
          className="inline-flex items-center gap-2 px-4 py-2 text-xs font-medium
                     border border-surface-border rounded-sm text-text-secondary
                     hover:text-text-primary hover:border-forest-900/30 transition-colors duration-150">
          <DownloadIcon className="w-3.5 h-3.5" /> Export Embedding (CSV)
        </button>
      </div>

      {/* 2D scatter — always shown */}
      <TSNEScatter2D result={result} />

      {/* 3D scatter — only for 3D results */}
      {result.n_components === 3 && <TSNEScatter3D result={result} />}

      {/* Feature list */}
      <FeatureList result={result} />
    </div>
  )
}

/* ═════════════════════════════════════════════════════════════════
   TSNEScatter2D
═════════════════════════════════════════════════════════════════ */
function TSNEScatter2D({ result }: { result: TsneResult }) {
  const hasCategory = result.category_labels.length > 0
  const uniqueLabels = useMemo(() => {
    if (!hasCategory) return []
    return [...new Set(result.category_labels)].sort()
  }, [hasCategory, result.category_labels])

  const { data, layout } = useMemo(() => {
    const makeLayout = () => ({
      paper_bgcolor: 'rgba(0,0,0,0)',
      plot_bgcolor:  'rgba(0,0,0,0)',
      font: { family: 'Inter, system-ui, sans-serif', size: 11, color: '#4A5E50' },
      margin: { t: 10, r: 10, b: 56, l: 56 },
      legend: { x: 0.02, y: 0.98, font: { size: 10 }, bgcolor: 'rgba(0,0,0,0)' },
      xaxis: {
        title: { text: 't-SNE 1', font: { size: 11, color: '#1C2A22' } },
        gridcolor: '#D2DCDB', linecolor: '#D2DCDB', zerolinecolor: '#D2DCDB', tickcolor: '#D2DCDB',
      },
      yaxis: {
        title: { text: 't-SNE 2', font: { size: 11, color: '#1C2A22' } },
        gridcolor: '#D2DCDB', linecolor: '#D2DCDB', zerolinecolor: '#D2DCDB', tickcolor: '#D2DCDB',
      },
    })

    if (hasCategory && uniqueLabels.length > 0) {
      const traces = uniqueLabels.map((label, idx) => {
        const color = colorFor(label, idx)
        const mask  = result.category_labels.map((l) => l === label)
        return {
          type: 'scatter' as const,
          mode: 'markers' as const,
          name: label,
          x: result.embedding.filter((_, i) => mask[i]).map((r) => r[0]),
          y: result.embedding.filter((_, i) => mask[i]).map((r) => r[1]),
          text: result.sample_ids.filter((_, i) => mask[i]),
          marker: { color, size: 9, line: { color: '#1C2A22', width: 0.5 }, opacity: 0.85 },
          hovertemplate: '<b>%{text}</b><br>t-SNE 1: %{x:.4f}<br>t-SNE 2: %{y:.4f}<br>' +
                         `Origin: ${label}<extra></extra>`,
        }
      })
      return { data: traces, layout: makeLayout() }
    } else {
      return {
        data: [{
          type: 'scatter' as const,
          mode: 'markers' as const,
          name: 'Samples',
          x: result.embedding.map((r) => r[0]),
          y: result.embedding.map((r) => r[1]),
          text: result.sample_ids,
          marker: { color: '#32493F', size: 9, line: { color: '#1C2A22', width: 0.5 }, opacity: 0.85 },
          hovertemplate: '<b>%{text}</b><br>t-SNE 1: %{x:.4f}<br>t-SNE 2: %{y:.4f}<extra></extra>',
        }],
        layout: makeLayout(),
      }
    }
  }, [result, hasCategory, uniqueLabels])

  return (
    <div className="border border-surface-border bg-brand-white">
      <div className="px-6 py-4 border-b border-surface-border">
        <h3 className="font-serif text-base text-text-primary">2D Embedding</h3>
        <p className="text-xs text-text-muted mt-0.5">
          Hover over a point to see its sample ID and coordinates.
          {hasCategory ? ' Colours represent botanical origin.' : ''}
        </p>
      </div>
      <div className="p-4">
        <PlotlyChart data={data} layout={layout} style={{ width: '100%', height: 480 }} />
      </div>
    </div>
  )
}

/* ═════════════════════════════════════════════════════════════════
   TSNEScatter3D
═════════════════════════════════════════════════════════════════ */
function TSNEScatter3D({ result }: { result: TsneResult }) {
  const hasCategory = result.category_labels.length > 0
  const uniqueLabels = useMemo(() => {
    if (!hasCategory) return []
    return [...new Set(result.category_labels)].sort()
  }, [hasCategory, result.category_labels])

  const { data, layout } = useMemo(() => {
    const axisStyle = {
      title: { font: { size: 11, color: '#1C2A22' } },
      gridcolor: '#D2DCDB', linecolor: '#D2DCDB', zerolinecolor: '#D2DCDB',
      backgroundcolor: 'rgba(0,0,0,0)',
    }
    const makeLayout = () => ({
      paper_bgcolor: 'rgba(0,0,0,0)',
      font: { family: 'Inter, system-ui, sans-serif', size: 11, color: '#4A5E50' },
      margin: { t: 10, r: 10, b: 10, l: 10 },
      legend: { font: { size: 10 }, bgcolor: 'rgba(0,0,0,0)' },
      scene: {
        xaxis: { ...axisStyle, title: { text: 't-SNE 1', ...axisStyle.title } },
        yaxis: { ...axisStyle, title: { text: 't-SNE 2', ...axisStyle.title } },
        zaxis: { ...axisStyle, title: { text: 't-SNE 3', ...axisStyle.title } },
        bgcolor: 'rgba(0,0,0,0)',
      },
    })

    if (hasCategory && uniqueLabels.length > 0) {
      const traces = uniqueLabels.map((label, idx) => {
        const color = colorFor(label, idx)
        const mask  = result.category_labels.map((l) => l === label)
        return {
          type: 'scatter3d' as const,
          mode: 'markers' as const,
          name: label,
          x: result.embedding.filter((_, i) => mask[i]).map((r) => r[0]),
          y: result.embedding.filter((_, i) => mask[i]).map((r) => r[1]),
          z: result.embedding.filter((_, i) => mask[i]).map((r) => r[2]),
          text: result.sample_ids.filter((_, i) => mask[i]),
          marker: { color, size: 5, line: { color: '#1C2A22', width: 0.3 }, opacity: 0.85 },
          hovertemplate: '<b>%{text}</b><br>t-SNE 1: %{x:.4f}<br>t-SNE 2: %{y:.4f}<br>' +
                         `t-SNE 3: %{z:.4f}<br>Origin: ${label}<extra></extra>`,
        }
      })
      return { data: traces, layout: makeLayout() }
    } else {
      return {
        data: [{
          type: 'scatter3d' as const,
          mode: 'markers' as const,
          name: 'Samples',
          x: result.embedding.map((r) => r[0]),
          y: result.embedding.map((r) => r[1]),
          z: result.embedding.map((r) => r[2]),
          text: result.sample_ids,
          marker: { color: '#32493F', size: 5, line: { color: '#1C2A22', width: 0.3 }, opacity: 0.85 },
          hovertemplate: '<b>%{text}</b><br>t-SNE 1: %{x:.4f}<br>t-SNE 2: %{y:.4f}<br>t-SNE 3: %{z:.4f}<extra></extra>',
        }],
        layout: makeLayout(),
      }
    }
  }, [result, hasCategory, uniqueLabels])

  return (
    <div className="border border-surface-border bg-brand-white">
      <div className="px-6 py-4 border-b border-surface-border">
        <h3 className="font-serif text-base text-text-primary">3D Embedding</h3>
        <p className="text-xs text-text-muted mt-0.5">
          Drag to rotate · Scroll to zoom · Hover for sample details.
          {hasCategory ? ' Colours represent botanical origin.' : ''}
        </p>
      </div>
      <div className="p-4">
        <PlotlyChart data={data} layout={layout} style={{ width: '100%', height: 520 }} />
      </div>
    </div>
  )
}

/* ═════════════════════════════════════════════════════════════════
   FeatureList — shows which measurement variables entered the matrix
═════════════════════════════════════════════════════════════════ */
function FeatureList({ result }: { result: TsneResult }) {
  return (
    <div className="border border-surface-border bg-brand-white">
      <div className="px-6 py-4 border-b border-surface-border">
        <h3 className="font-serif text-base text-text-primary">
          Measurement Variables in Embedding ({result.feature_columns.length})
        </h3>
        <p className="text-xs text-text-muted mt-0.5">
          These are the only columns that entered the numerical feature matrix.
          sample_id and category columns are excluded.
        </p>
      </div>
      <div className="px-6 py-4 flex flex-wrap gap-2">
        {result.feature_columns.map((col) => (
          <span key={col}
            className="inline-flex items-center px-3 py-1.5 rounded-sm border
                       text-xs font-mono text-text-secondary border-surface-border
                       bg-surface-overlay/30">
            {col}
          </span>
        ))}
      </div>
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

function ScatterIcon({ className = '' }: { className?: string }) {
  return (
    <svg viewBox="0 0 16 16" fill="none" className={className} xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
      <circle cx="4"  cy="11" r="1.5" stroke="currentColor" strokeWidth="1.3" />
      <circle cx="8"  cy="5"  r="1.5" stroke="currentColor" strokeWidth="1.3" />
      <circle cx="12" cy="9"  r="1.5" stroke="currentColor" strokeWidth="1.3" />
      <circle cx="6"  cy="8"  r="1.5" stroke="currentColor" strokeWidth="1.3" />
      <circle cx="10" cy="12" r="1.5" stroke="currentColor" strokeWidth="1.3" />
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

function DownloadIcon({ className = '' }: { className?: string }) {
  return (
    <svg viewBox="0 0 16 16" fill="none" className={className} xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
      <path d="M8 2v8M5 7l3 3 3-3M2 13h12" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" strokeLinejoin="round" />
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

function InfoIcon({ className = '' }: { className?: string }) {
  return (
    <svg viewBox="0 0 16 16" fill="none" className={className} xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
      <circle cx="8" cy="8" r="6.5" stroke="currentColor" strokeWidth="1.3" />
      <path d="M8 7.5v4M8 5.5v.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
    </svg>
  )
}
