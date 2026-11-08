import { useState } from 'react'
import type { ColumnInfo, ColumnRole } from '../api/datasets'

const ROLES: { value: ColumnRole; label: string; desc: string; color: string }[] = [
  {
    value: 'sensor',
    label: 'Sensor',
    desc:  'Numeric measurement — enters the feature matrix for PCA / t-SNE',
    color: 'bg-forest-900/[0.07] text-forest-900 border-forest-900/20',
  },
  {
    value: 'sample_id',
    label: 'Sample ID',
    desc:  'Unique row identifier — never used as a feature',
    color: 'bg-sage-200 text-forest-800 border-sage-400',
  },
  {
    value: 'category',
    label: 'Category',
    desc:  'Herbal category label — metadata only, used post-analysis',
    color: 'bg-surface-overlay text-text-secondary border-surface-border',
  },
  {
    value: 'ignored',
    label: 'Ignored',
    desc:  'Excluded from all analysis',
    color: 'bg-surface-overlay text-text-muted border-surface-border',
  },
]

interface Props {
  columns:  ColumnInfo[]
  onConfirm: (roles: Record<string, ColumnRole>) => void
  confirming?: boolean
}

export default function ColumnRoleEditor({ columns, onConfirm, confirming = false }: Props) {
  const [roles, setRoles] = useState<Record<string, ColumnRole>>(
    () => Object.fromEntries(columns.map((c) => [c.name, c.detected_role]))
  )

  const sensorCount  = Object.values(roles).filter((r) => r === 'sensor').length
  const sampleCount  = Object.values(roles).filter((r) => r === 'sample_id').length
  const catCount     = Object.values(roles).filter((r) => r === 'category').length

  return (
    <div>
      {/* Header */}
      <div className="px-6 py-4 border-b border-surface-border flex items-center justify-between gap-4">
        <div>
          <h3 className="font-serif text-base text-text-primary">Confirm Column Roles</h3>
          <p className="text-xs text-text-muted mt-0.5">
            Review the automatic detection and correct any misclassifications before proceeding.
          </p>
        </div>

        {/* Summary pills */}
        <div className="flex gap-2 shrink-0">
          <RoleSummaryPill count={sensorCount}  label="Sensors" color="bg-forest-900/[0.07] text-forest-900 border-forest-900/20" />
          <RoleSummaryPill count={sampleCount}  label="IDs"     color="bg-sage-200 text-forest-800 border-sage-400" />
          <RoleSummaryPill count={catCount}     label="Labels"  color="bg-surface-overlay text-text-secondary border-surface-border" />
        </div>
      </div>

      {/* Scientific safeguard notice */}
      {sensorCount === 0 && (
        <div className="mx-6 mt-4 flex items-start gap-2 px-4 py-3
                        bg-amber-50 border border-amber-200 rounded-sm">
          <WarnSvg className="w-4 h-4 text-amber-600 shrink-0 mt-0.5" />
          <p className="text-sm text-amber-800">
            No columns are assigned as sensors. At least one sensor column is required
            before running PCA or t-SNE analysis.
          </p>
        </div>
      )}

      {/* Column table */}
      <div className="overflow-x-auto">
        <table className="w-full text-sm border-collapse">
          <thead>
            <tr className="border-b border-surface-border bg-surface-overlay">
              <th className="text-left px-6 py-3 text-xs font-medium tracking-[0.1em] uppercase text-text-muted">Column</th>
              <th className="text-left px-4 py-3 text-xs font-medium tracking-[0.1em] uppercase text-text-muted">Type</th>
              <th className="text-right px-4 py-3 text-xs font-medium tracking-[0.1em] uppercase text-text-muted">Missing</th>
              <th className="text-left px-4 py-3 text-xs font-medium tracking-[0.1em] uppercase text-text-muted">Sample values</th>
              <th className="text-left px-6 py-3 text-xs font-medium tracking-[0.1em] uppercase text-text-muted">Role</th>
            </tr>
          </thead>
          <tbody>
            {columns.map((col, i) => (
              <tr key={col.name}
                  className={`border-b border-surface-border last:border-0 ${i % 2 === 0 ? 'bg-brand-white' : 'bg-surface-overlay/40'}`}>
                {/* Column name */}
                <td className="px-6 py-3 font-mono text-xs text-text-primary font-medium max-w-[160px] truncate">
                  {col.name}
                </td>
                {/* Dtype */}
                <td className="px-4 py-3 font-mono text-xs text-text-muted whitespace-nowrap">
                  {col.dtype}
                </td>
                {/* Missing */}
                <td className="px-4 py-3 text-right">
                  {col.missing_count > 0 ? (
                    <span className="text-xs text-amber-700 font-medium">{col.missing_count}</span>
                  ) : (
                    <span className="text-xs text-text-muted">—</span>
                  )}
                </td>
                {/* Sample values */}
                <td className="px-4 py-3 max-w-[200px]">
                  <span className="text-xs text-text-muted truncate block">
                    {col.sample_values.slice(0, 3).map(String).join(', ')}
                    {col.sample_values.length > 3 ? ' …' : ''}
                  </span>
                </td>
                {/* Role selector */}
                <td className="px-6 py-3">
                  <RoleSelector
                    value={roles[col.name]}
                    onChange={(r) => setRoles((prev) => ({ ...prev, [col.name]: r }))}
                  />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Confirm button */}
      <div className="px-6 py-4 border-t border-surface-border flex items-center justify-between gap-4">
        <p className="text-xs text-text-muted">
          Category labels will <strong>not</strong> enter the PCA or t-SNE feature matrix.
        </p>
        <button
          onClick={() => onConfirm(roles)}
          disabled={confirming || sensorCount === 0}
          className={[
            'inline-flex items-center gap-2 px-5 py-2.5 text-sm font-medium rounded-sm',
            'transition-colors duration-200',
            confirming || sensorCount === 0
              ? 'bg-surface-border text-text-muted cursor-not-allowed'
              : 'bg-forest-900 text-text-inverse hover:bg-forest-800',
          ].join(' ')}
        >
          {confirming ? 'Saving…' : 'Confirm Roles'}
          {!confirming && <CheckSvg className="w-4 h-4" />}
        </button>
      </div>
    </div>
  )
}

/* ── Sub-components ──────────────────────────────────────────── */

function RoleSelector({
  value, onChange,
}: { value: ColumnRole; onChange: (r: ColumnRole) => void }) {
  return (
    <select
      value={value}
      onChange={(e) => onChange(e.target.value as ColumnRole)}
      className="text-xs border border-surface-border bg-brand-white text-text-primary
                 rounded-sm px-2.5 py-1.5 focus:outline-none focus:ring-1
                 focus:ring-forest-900/30 cursor-pointer"
    >
      {ROLES.map((r) => (
        <option key={r.value} value={r.value}>{r.label}</option>
      ))}
    </select>
  )
}

function RoleSummaryPill({
  count, label, color,
}: { count: number; label: string; color: string }) {
  return (
    <span className={`inline-flex items-center gap-1 px-2.5 py-1 text-[10px] font-medium
                      tracking-wide uppercase rounded-sm border ${color}`}>
      <span className="font-bold">{count}</span> {label}
    </span>
  )
}

function WarnSvg({ className = '' }: { className?: string }) {
  return (
    <svg viewBox="0 0 16 16" fill="none" className={className}
         xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
      <path d="M8 2L14.5 13.5H1.5L8 2Z" stroke="currentColor" strokeWidth="1.3"
            strokeLinejoin="round"/>
      <path d="M8 6.5v3M8 11v.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
    </svg>
  )
}

function CheckSvg({ className = '' }: { className?: string }) {
  return (
    <svg viewBox="0 0 16 16" fill="none" className={className}
         xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
      <path d="M3 8l4 4 6-7" stroke="currentColor"
            strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round"/>
    </svg>
  )
}
