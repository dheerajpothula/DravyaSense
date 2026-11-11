import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  ApiError,
  type DatasetSummary,
  type StatisticsResponse,
  getStatistics,
  listDatasets,
} from '../../api/datasets'
import SensorStatsTable from '../../components/SensorStatsTable'
import SensorDistributionChart from '../../components/SensorDistributionChart'
import PlotlyChart from '../../components/PlotlyChart'

/**
 * Data Explorer — Module 02
 *
 * Provides descriptive statistics and distribution visualisations for
 * uploaded sensor datasets.  Sensor channels are identified dynamically
 * from the stored column-role assignments — no channel names are hardcoded.
 *
 * sample_id and category columns are never included in statistics.
 */

export default function DataExplorerPage() {
  // ── State ─────────────────────────────────────────────────────
  const [datasets,     setDatasets]     = useState<DatasetSummary[]>([])
  const [selectedId,   setSelectedId]   = useState<string | null>(null)
  const [stats,        setStats]        = useState<StatisticsResponse | null>(null)
  const [listLoading,  setListLoading]  = useState(true)
  const [statsLoading,  setStatsLoading] = useState(false)
  const [error,         setError]        = useState<string | null>(null)

  const selected = datasets.find((d) => d.id === selectedId) ?? null

  // ── Dataset classification ────────────────────────────────────
  // Use stored measurement_type metadata if available; fall back to
  // filename only for legacy datasets that pre-date the metadata field.
  // A dataset is the development benchmark only when it has NO
  // measurement_type set AND its filename is exactly 'electronic_tongue.csv'.
  const hasType    = !!selected?.measurement_type
  const isBenchmark = selected
    ? !hasType && selected.original_filename.toLowerCase() === 'electronic_tongue.csv'
    : false
  const isResearch  = selected ? !!selected.measurement_type : false

  // ── Load dataset list on mount ───────────────────────────────
  useEffect(() => {
    listDatasets()
      .then((list) => {
        setDatasets(list)
        setListLoading(false)
        if (list.length > 0) {
          setSelectedId(list[0].id)  // default to most recent
        }
      })
      .catch(() => {
        setListLoading(false)
        setError('Could not load datasets. Is the backend running?')
      })
  }, [])

  // ── Load statistics when dataset changes ──────────────────────
  useEffect(() => {
    if (!selectedId) return
    setStatsLoading(true)
    setError(null)
    setStats(null)
    getStatistics(selectedId)
      .then((result) => {
        setStats(result)
        setStatsLoading(false)
      })
      .catch((err) => {
        const msg = err instanceof ApiError ? err.message : 'Could not load statistics.'
        setError(msg)
        setStatsLoading(false)
      })
  }, [selectedId])

  // ── Box plot data (precomputed from statistics) ──────────────
  const boxPlot = useMemo(() => {
    if (!stats || stats.statistics.length === 0) return null
    const valid = stats.statistics.filter((s) => s.count > 0)
    if (valid.length === 0) return null

    return {
      data: [{
        type: 'box',
        x:          valid.map((s) => s.column),
        q1:         valid.map((s) => s.q1),
        median:     valid.map((s) => s.median),
        q3:         valid.map((s) => s.q3),
        lowerfence: valid.map((s) => s.min),
        upperfence: valid.map((s) => s.max),
        mean:       valid.map((s) => s.mean),
        sd:         valid.map((s) => s.std),
        boxpoints:  false,
        marker:     { color: '#32493F' },
        line:       { color: '#1C2A22' },
        fillcolor:  '#D2DCDB',
        showlegend: false,
      }],
      layout: {
        paper_bgcolor: 'rgba(0,0,0,0)',
        plot_bgcolor:  'rgba(0,0,0,0)',
        font: {
          family: 'Inter, system-ui, sans-serif',
          size: 11,
          color: '#4A5E50',
        },
        margin: { t: 20, r: 20, b: 44, l: 64 },
        xaxis: {
          gridcolor:    '#D2DCDB',
          linecolor:    '#D2DCDB',
          zerolinecolor: '#D2DCDB',
          tickcolor:    '#D2DCDB',
          title: { text: 'Sensor Channel', font: { size: 11, color: '#1C2A22' } },
        },
        yaxis: {
          gridcolor:    '#D2DCDB',
          linecolor:    '#D2DCDB',
          zerolinecolor: '#D2DCDB',
          tickcolor:    '#D2DCDB',
          title: { text: 'Value', font: { size: 11, color: '#1C2A22' } },
        },
        boxmode: 'group',
      },
    }
  }, [stats])

  /* ── Render ──────────────────────────────────────────────── */
  return (
    <div className="flex flex-col gap-8">

      {/* ── Page header ─────────────────────────────────────── */}
      <div className="pb-6 border-b border-surface-border">
        <p className="eyebrow mb-3">
          <span className="w-5 h-px bg-text-muted inline-block" />
          Module 02
        </p>
        <h1 className="font-serif text-display-sm text-text-primary mb-2 leading-tight">
          Data Explorer
        </h1>
        <p className="text-text-secondary text-sm leading-relaxed max-w-xl">
          Preview raw data, descriptive statistics, and distribution plots.
          Sensor channels are identified dynamically from the stored column
          roles — sample_id and category columns are excluded from all computations.
        </p>
      </div>

      {/* ── Dataset list loading ────────────────────────────── */}
      {listLoading && (
        <div className="border border-surface-border bg-brand-white p-8
                        flex items-center justify-center">
          <div className="w-5 h-5 border-2 border-surface-border border-t-forest-900
                          rounded-full animate-spin" />
        </div>
      )}

      {/* ── No datasets ─────────────────────────────────────── */}
      {!listLoading && datasets.length === 0 && (
        <div className="border border-surface-border bg-brand-white p-8 text-center">
          <p className="text-sm font-medium text-text-primary mb-1">No datasets uploaded yet</p>
          <p className="text-xs text-text-muted mb-4">
            Upload a dataset in the Dataset Management module to begin exploring.
          </p>
          <Link
            to="/dashboard/datasets"
            className="inline-flex items-center gap-2 px-4 py-2 text-sm font-medium
                       bg-forest-900 text-text-inverse rounded-sm
                       hover:bg-forest-800 transition-colors duration-200"
          >
            Go to Dataset Management
          </Link>
        </div>
      )}

      {/* ── Dataset selector + content ───────────────────────── */}
      {!listLoading && datasets.length > 0 && (
        <>
          {/* Dataset selector bar */}
          <div className="border border-surface-border bg-brand-white">
            <div className="px-6 py-4 flex items-center gap-4 flex-wrap">
              <label className="text-xs font-medium text-text-muted uppercase
                                tracking-[0.1em] shrink-0">
                Dataset
              </label>
              <select
                value={selectedId ?? ''}
                onChange={(e) => setSelectedId(e.target.value)}
                className="text-sm border border-surface-border bg-brand-white text-text-primary
                           rounded-sm px-3 py-2 focus:outline-none focus:ring-1
                           focus:ring-forest-900/30 cursor-pointer min-w-[260px]"
              >
                {datasets.map((ds) => (
                  <option key={ds.id} value={ds.id}>
                    {ds.original_filename} — {ds.row_count} rows · {ds.sensor_column_count} sensors
                  </option>
                ))}
              </select>

              {selected && (
                <div className="flex items-center gap-3 flex-wrap">
                  <span className="text-xs text-text-muted">
                    {selected.row_count} rows · {selected.sensor_column_count} sensors
                    {selected.missing_value_count > 0
                      ? ` · ${selected.missing_value_count} missing`
                      : ''}
                  </span>
                  {isBenchmark && (
                    <span className="inline-flex items-center px-2 py-0.5 text-[10px]
                                     font-medium tracking-wide uppercase rounded-sm border
                                     bg-sage-200 text-forest-800 border-sage-400">
                      Development Benchmark
                    </span>
                  )}
                  {isResearch && (
                    <span className="inline-flex items-center px-2 py-0.5 text-[10px]
                                     font-medium tracking-wide uppercase rounded-sm border
                                     bg-forest-900/[0.07] text-forest-900 border-forest-900/20">
                      Research Dataset
                    </span>
                  )}
                </div>
              )}
            </div>
          </div>

          {/* Benchmark notice */}
          {isBenchmark && (
            <div className="flex items-start gap-3 px-5 py-4
                            bg-surface-overlay border border-surface-border rounded-sm">
              <InfoIcon className="w-4 h-4 text-text-muted shrink-0 mt-0.5" />
              <p className="text-sm text-text-secondary leading-relaxed">
                <span className="font-medium text-text-primary">Development Benchmark.</span>
                {' '}This electronic-tongue dataset is used for development and testing
                purposes — it is not herbal research data.
              </p>
            </div>
          )}

          {/* Research dataset notice */}
          {isResearch && selected && (
            <div className="flex items-start gap-3 px-5 py-4
                            bg-forest-900/[0.04] border border-forest-900/15 rounded-sm">
              <InfoIcon className="w-4 h-4 text-forest-900 shrink-0 mt-0.5" />
              <div className="text-sm text-text-secondary leading-relaxed">
                <span className="font-medium text-text-primary">Research Dataset</span>
                {selected.measurement_type && (
                  <span className="text-text-muted">
                    {' — '}
                    {selected.measurement_type === 'electronic_tongue' && 'Electronic Tongue'}
                    {selected.measurement_type === 'electronic_nose'   && 'Electronic Nose'}
                    {selected.measurement_type === 'chemical_analysis' && 'Chemical Analysis'}
                  </span>
                )}
                {selected.source_attribution && (
                  <p className="mt-0.5 text-xs text-text-muted">{selected.source_attribution}</p>
                )}
              </div>
            </div>
          )}

          {/* Stats loading */}
          {statsLoading && (
            <div className="border border-surface-border bg-brand-white p-8
                            flex flex-col items-center gap-3 text-center">
              <div className="w-6 h-6 border-2 border-surface-border border-t-forest-900
                              rounded-full animate-spin" />
              <p className="text-sm text-text-secondary">Computing statistics…</p>
            </div>
          )}

          {/* Error */}
          {error && (
            <div className="flex items-start gap-2 px-4 py-3
                            bg-red-50 border border-red-200 rounded-sm">
              <ErrorIcon className="w-4 h-4 text-red-500 shrink-0 mt-0.5" />
              <p className="text-sm text-red-700">{error}</p>
            </div>
          )}

          {/* Statistics + charts */}
          {stats && !statsLoading && (
            <>
              {/* No sensors warning */}
              {stats.statistics.length === 0 && (
                <div className="flex items-start gap-2 px-4 py-3
                                bg-amber-50 border border-amber-200 rounded-sm">
                  <WarnIcon className="w-4 h-4 text-amber-600 shrink-0 mt-0.5" />
                  <p className="text-sm text-amber-800">
                    No sensor columns found in this dataset. Assign sensor roles
                    in the Dataset Management module before exploring.
                  </p>
                </div>
              )}

              {/* Descriptive statistics table */}
              {stats.statistics.length > 0 && (
                <SensorStatsTable statistics={stats.statistics} />
              )}

              {/* Sensor distributions (histograms) */}
              {stats.statistics.length > 0 && (
                <div>
                  <h2 className="font-serif text-lg text-text-primary mb-4">
                    Sensor Distributions
                  </h2>
                  <div className="grid sm:grid-cols-2 xl:grid-cols-3 gap-4">
                    {stats.statistics.map((s) => (
                      <SensorDistributionChart key={s.column} stats={s} />
                    ))}
                  </div>
                </div>
              )}

              {/* Box plot comparison */}
              {boxPlot && (
                <div>
                  <h2 className="font-serif text-lg text-text-primary mb-4">
                    Box Plot Comparison
                  </h2>
                  <div className="border border-surface-border bg-brand-white">
                    <div className="px-6 py-3 border-b border-surface-border">
                      <p className="text-xs text-text-muted">
                        Quartile-based comparison across all sensor channels.
                        Whiskers extend to min and max values.
                      </p>
                    </div>
                    <div className="p-4">
                      <PlotlyChart
                        data={boxPlot.data}
                        layout={boxPlot.layout}
                        style={{ width: '100%', height: 360 }}
                      />
                    </div>
                  </div>
                </div>
              )}
            </>
          )}
        </>
      )}
    </div>
  )
}


/* ── Icons ──────────────────────────────────────────────────────── */

function InfoIcon({ className = '' }: { className?: string }) {
  return (
    <svg viewBox="0 0 16 16" fill="none" className={className}
         xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
      <circle cx="8" cy="8" r="6.5" stroke="currentColor" strokeWidth="1.3"/>
      <path d="M8 7.5v4M8 5.5v.5" stroke="currentColor"
            strokeWidth="1.5" strokeLinecap="round"/>
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
