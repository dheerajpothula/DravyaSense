import type { DatasetPreview } from '../api/datasets'

interface Props {
  preview:   DatasetPreview
  page:      number
  onPage:    (p: number) => void
  loading?:  boolean
}

export default function DataPreviewTable({ preview, page, onPage, loading = false }: Props) {
  const totalPages = Math.ceil(preview.total_rows / preview.page_size)
  const start = (page - 1) * preview.page_size + 1
  const end   = Math.min(page * preview.page_size, preview.total_rows)

  return (
    <div>
      {/* Table */}
      <div className={`overflow-x-auto transition-opacity duration-200 ${loading ? 'opacity-50' : ''}`}>
        <table className="w-full text-xs border-collapse">
          <thead>
            <tr className="bg-surface-overlay border-b border-surface-border">
              {/* Row number */}
              <th className="px-4 py-2.5 text-right text-text-muted font-medium w-12 border-r border-surface-border">
                #
              </th>
              {preview.columns.map((col) => (
                <th key={col}
                    className="px-4 py-2.5 text-left font-medium text-text-primary
                               whitespace-nowrap border-r border-surface-border last:border-r-0">
                  {col}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {preview.rows.map((row, ri) => {
              const absoluteRow = start + ri
              return (
                <tr key={ri}
                    className={`border-b border-surface-border last:border-0 ${ri % 2 === 0 ? 'bg-brand-white' : 'bg-surface-overlay/30'}`}>
                  {/* Row number */}
                  <td className="px-4 py-2 text-right font-mono text-text-muted border-r border-surface-border">
                    {absoluteRow}
                  </td>
                  {row.map((cell, ci) => (
                    <td key={ci}
                        className={[
                          'px-4 py-2 border-r border-surface-border last:border-r-0',
                          cell === null ? 'text-amber-600' : 'text-text-secondary',
                        ].join(' ')}>
                      {cell === null
                        ? <span className="italic font-mono text-[10px]">null</span>
                        : String(cell)}
                    </td>
                  ))}
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      <div className="flex items-center justify-between px-4 py-3
                      border-t border-surface-border bg-surface-overlay/40">
        <p className="text-xs text-text-muted">
          Rows {start}–{end} of {preview.total_rows}
        </p>
        <div className="flex items-center gap-1">
          <PageBtn
            label="‹ Prev"
            disabled={page <= 1 || loading}
            onClick={() => onPage(page - 1)}
          />
          <span className="px-3 py-1 text-xs text-text-muted">
            {page} / {totalPages}
          </span>
          <PageBtn
            label="Next ›"
            disabled={page >= totalPages || loading}
            onClick={() => onPage(page + 1)}
          />
        </div>
      </div>
    </div>
  )
}

function PageBtn({
  label, onClick, disabled,
}: { label: string; onClick: () => void; disabled: boolean }) {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      className={[
        'px-3 py-1 text-xs border border-surface-border rounded-sm',
        'transition-colors duration-150',
        disabled
          ? 'text-text-muted cursor-not-allowed'
          : 'text-text-primary hover:bg-surface-overlay cursor-pointer',
      ].join(' ')}
    >
      {label}
    </button>
  )
}
