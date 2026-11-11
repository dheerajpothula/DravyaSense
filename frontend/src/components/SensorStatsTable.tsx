import type { SensorStatistics } from '../api/datasets'

/**
 * Descriptive statistics table — one row per sensor channel.
 * Horizontally scrollable to accommodate all statistical measures.
 */

interface Props {
  statistics: SensorStatistics[]
}

/* ── Formatting helpers ────────────────────────────────────────── */

function fmt(n: number, decimals = 2): string {
  if (Number.isNaN(n) || !Number.isFinite(n)) return '—'
  return n.toLocaleString('en-US', {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  })
}

/* ── Column definitions ────────────────────────────────────────── */

interface ColDef {
  key:  string
  label: string
  decimals: number
}

const COLS: ColDef[] = [
  { key: 'count',    label: 'Count',    decimals: 0 },
  { key: 'mean',     label: 'Mean',     decimals: 2 },
  { key: 'std',      label: 'Std',      decimals: 2 },
  { key: 'min',      label: 'Min',      decimals: 2 },
  { key: 'q1',       label: 'Q1',       decimals: 2 },
  { key: 'median',   label: 'Median',   decimals: 2 },
  { key: 'q3',       label: 'Q3',       decimals: 2 },
  { key: 'max',      label: 'Max',      decimals: 2 },
  { key: 'variance', label: 'Variance', decimals: 2 },
  { key: 'skewness', label: 'Skew',     decimals: 3 },
  { key: 'kurtosis', label: 'Kurtosis', decimals: 3 },
  { key: 'missing_count', label: 'Missing', decimals: 0 },
]

/* ── Component ─────────────────────────────────────────────────── */

export default function SensorStatsTable({ statistics }: Props) {
  return (
    <div className="border border-surface-border bg-brand-white">
      <div className="px-6 py-4 border-b border-surface-border">
        <h3 className="font-serif text-base text-text-primary">Descriptive Statistics</h3>
        <p className="text-xs text-text-muted mt-0.5">
          Per-sensor summary computed from stored measurements. sample_id and
          category columns are excluded.
        </p>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-xs border-collapse">
          <thead>
            <tr className="border-b border-surface-border bg-surface-overlay">
              <th className="text-left px-4 py-2.5 font-medium tracking-[0.08em]
                             uppercase text-text-muted whitespace-nowrap sticky left-0
                             bg-surface-overlay z-10">
                Sensor
              </th>
              {COLS.map((c) => (
                <th key={c.key}
                    className="text-right px-4 py-2.5 font-medium tracking-[0.08em]
                               uppercase text-text-muted whitespace-nowrap">
                  {c.label}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {statistics.map((s, i) => (
              <tr key={s.column}
                  className={`border-b border-surface-border last:border-0
                              ${i % 2 === 0 ? 'bg-brand-white' : 'bg-surface-overlay/30'}`}>
                <td className={`px-4 py-2.5 font-mono font-medium text-text-primary
                              whitespace-nowrap sticky left-0 z-10
                              ${i % 2 === 0 ? 'bg-brand-white' : 'bg-surface-overlay/30'}`}>
                  {s.column}
                </td>
                {COLS.map((c) => {
                  const value = (s as any)[c.key] as number
                  const warn = c.key === 'missing_count' && value > 0
                  return (
                    <td key={c.key}
                        className={`px-4 py-2.5 text-right font-mono whitespace-nowrap
                                    ${warn ? 'text-amber-700' : 'text-text-secondary'}`}>
                      {fmt(value, c.decimals)}
                    </td>
                  )
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
