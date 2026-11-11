import { useMemo } from 'react'
import type { SensorStatistics } from '../api/datasets'
import PlotlyChart from './PlotlyChart'

/**
 * Sensor distribution card — renders a histogram from pre-computed
 * bin data returned by the backend.  Key statistics are shown inline
 * below the chart for quick reference.
 */

interface Props {
  stats: SensorStatistics
}

/* ── Formatting helper ─────────────────────────────────────────── */

function fmt(n: number, decimals = 1): string {
  if (Number.isNaN(n) || !Number.isFinite(n)) return '—'
  return n.toLocaleString('en-US', {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  })
}

/* ── Component ─────────────────────────────────────────────────── */

export default function SensorDistributionChart({ stats }: Props) {
  const { data, layout } = useMemo(() => {
    const n = stats.histogram.bin_centers.length
    const binWidth = n > 0
      ? (stats.histogram.bin_edges[1] - stats.histogram.bin_edges[0]) * 0.95
      : 1

    return {
      data: [{
        type: 'bar',
        x: stats.histogram.bin_centers,
        y: stats.histogram.frequencies,
        width: Array(n).fill(binWidth),
        marker: {
          color: '#32493F',
          line: { color: '#1C2A22', width: 0.5 },
        },
      }],
      layout: {
        paper_bgcolor: 'rgba(0,0,0,0)',
        plot_bgcolor: 'rgba(0,0,0,0)',
        font: {
          family: 'Inter, system-ui, sans-serif',
          size: 9,
          color: '#4A5E50',
        },
        margin: { t: 8, r: 10, b: 36, l: 38 },
        bargap: 0.03,
        xaxis: {
          gridcolor: '#D2DCDB',
          linecolor: '#D2DCDB',
          zerolinecolor: '#D2DCDB',
          tickcolor: '#D2DCDB',
          tickfont: { size: 8 },
          title: {
            text: stats.column,
            font: { size: 10, color: '#1C2A22', family: 'Inter, system-ui, sans-serif' },
          },
        },
        yaxis: {
          gridcolor: '#D2DCDB',
          linecolor: '#D2DCDB',
          zerolinecolor: '#D2DCDB',
          tickcolor: '#D2DCDB',
          tickfont: { size: 8 },
          title: {
            text: 'Frequency',
            font: { size: 9, color: '#8A9E90', family: 'Inter, system-ui, sans-serif' },
          },
        },
      },
    }
  }, [stats])

  // ── Empty histogram (all values missing) ────────────────────
  if (stats.histogram.frequencies.length === 0) {
    return (
      <div className="border border-surface-border bg-brand-white flex flex-col">
        <div className="px-4 py-3 border-b border-surface-border">
          <h4 className="font-mono text-sm font-medium text-text-primary">
            {stats.column}
          </h4>
        </div>
        <div className="flex-1 flex items-center justify-center p-8">
          <p className="text-xs text-amber-700">
            All {stats.missing_count} values missing — no distribution to display.
          </p>
        </div>
      </div>
    )
  }

  return (
    <div className="border border-surface-border bg-brand-white flex flex-col">
      {/* Header */}
      <div className="px-4 py-2.5 border-b border-surface-border flex items-center justify-between">
        <h4 className="font-mono text-sm font-medium text-text-primary">
          {stats.column}
        </h4>
        <span className="text-[10px] font-mono text-text-muted">
          n={stats.count}
        </span>
      </div>

      {/* Chart */}
      <div className="p-2">
        <PlotlyChart data={data} layout={layout} style={{ width: '100%', height: 200 }} />
      </div>

      {/* Inline stats */}
      <div className="grid grid-cols-4 border-t border-surface-border text-center">
        <InlineStat label="Mean"  value={fmt(stats.mean)} />
        <InlineStat label="Std"   value={fmt(stats.std)} />
        <InlineStat label="Min"   value={fmt(stats.min, 0)} />
        <InlineStat label="Max"   value={fmt(stats.max, 0)} />
      </div>
    </div>
  )
}

/* ── Sub-component ──────────────────────────────────────────────── */

function InlineStat({ label, value }: { label: string; value: string }) {
  return (
    <div className="px-2 py-2 border-r border-surface-border last:border-r-0">
      <p className="text-[9px] text-text-muted uppercase tracking-wide">{label}</p>
      <p className="text-xs font-mono text-text-primary mt-0.5">{value}</p>
    </div>
  )
}
