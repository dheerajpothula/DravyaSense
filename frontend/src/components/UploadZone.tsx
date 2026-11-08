import { useCallback, useRef, useState } from 'react'

interface Props {
  onFile: (file: File) => void
  disabled?: boolean
}

const ACCEPTED_EXTS = ['.csv', '.xlsx']
const ACCEPTED_MIME = [
  'text/csv',
  'application/csv',
  'application/vnd.ms-excel',
  'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
]

/** Validate file before handing it to the parent. */
function validateFile(file: File): string | null {
  const name = file.name.toLowerCase()
  const validExt = ACCEPTED_EXTS.some((e) => name.endsWith(e))
  if (!validExt) {
    return `"${file.name}" is not a supported file type. Please upload a CSV or Excel (.xlsx) file.`
  }
  const MAX_MB = 50
  if (file.size > MAX_MB * 1024 * 1024) {
    return `File is too large (${(file.size / 1_048_576).toFixed(1)} MB). Maximum allowed size is ${MAX_MB} MB.`
  }
  if (file.size === 0) {
    return 'The selected file is empty.'
  }
  return null
}

export default function UploadZone({ onFile, disabled = false }: Props) {
  const [dragging, setDragging]   = useState(false)
  const [localError, setLocalErr] = useState<string | null>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  const handleFile = useCallback(
    (file: File) => {
      setLocalErr(null)
      const err = validateFile(file)
      if (err) { setLocalErr(err); return }
      onFile(file)
    },
    [onFile],
  )

  const onDragOver = (e: React.DragEvent) => {
    e.preventDefault()
    if (!disabled) setDragging(true)
  }
  const onDragLeave = () => setDragging(false)
  const onDrop = (e: React.DragEvent) => {
    e.preventDefault()
    setDragging(false)
    if (disabled) return
    const file = e.dataTransfer.files[0]
    if (file) handleFile(file)
  }
  const onInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (file) handleFile(file)
    e.target.value = '' // allow re-selecting same file
  }

  return (
    <div>
      <div
        role="button"
        tabIndex={disabled ? -1 : 0}
        aria-label="Upload dataset — drag and drop or click to browse"
        onDragOver={onDragOver}
        onDragLeave={onDragLeave}
        onDrop={onDrop}
        onClick={() => !disabled && inputRef.current?.click()}
        onKeyDown={(e) => {
          if ((e.key === 'Enter' || e.key === ' ') && !disabled)
            inputRef.current?.click()
        }}
        className={[
          'relative border-2 border-dashed rounded-sm px-8 py-12',
          'flex flex-col items-center justify-center text-center gap-4',
          'transition-colors duration-200',
          disabled
            ? 'border-surface-border bg-surface-overlay cursor-not-allowed opacity-60'
            : dragging
              ? 'border-forest-700 bg-sage-100/60 cursor-copy'
              : 'border-surface-border bg-brand-white cursor-pointer hover:border-forest-700 hover:bg-sage-100/40',
        ].join(' ')}
      >
        {/* Icon */}
        <div className={[
          'w-12 h-12 rounded-sm flex items-center justify-center',
          dragging ? 'bg-forest-900' : 'bg-surface-overlay',
          'transition-colors duration-200',
        ].join(' ')}>
          <UploadSvg className={`w-6 h-6 ${dragging ? 'text-text-inverse' : 'text-text-muted'}`} />
        </div>

        {/* Text */}
        <div>
          <p className="text-sm font-medium text-text-primary mb-1">
            {dragging ? 'Drop to upload' : 'Drag your dataset here'}
          </p>
          <p className="text-xs text-text-muted">
            or{' '}
            <span className="text-text-primary underline underline-offset-2 decoration-dotted">
              click to browse
            </span>
          </p>
        </div>

        {/* Accepted formats */}
        <div className="flex gap-2">
          {['CSV', 'XLSX'].map((fmt) => (
            <span key={fmt}
                  className="px-2 py-0.5 text-[10px] font-mono font-medium
                             bg-surface-overlay border border-surface-border
                             text-text-muted rounded-sm">
              {fmt}
            </span>
          ))}
          <span className="px-2 py-0.5 text-[10px] font-medium
                           bg-surface-overlay border border-surface-border
                           text-text-muted rounded-sm">
            Max 50 MB
          </span>
        </div>
      </div>

      {/* Client-side validation error */}
      {localError && (
        <div className="mt-3 flex items-start gap-2 px-4 py-3
                        bg-red-50 border border-red-200 rounded-sm">
          <ErrorSvg className="w-4 h-4 text-red-500 shrink-0 mt-0.5" />
          <p className="text-sm text-red-700">{localError}</p>
        </div>
      )}

      <input
        ref={inputRef}
        type="file"
        accept={ACCEPTED_EXTS.join(',') + ',' + ACCEPTED_MIME.join(',')}
        className="sr-only"
        onChange={onInputChange}
        disabled={disabled}
        aria-hidden="true"
      />
    </div>
  )
}

function UploadSvg({ className = '' }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" className={className}
         xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
      <path d="M12 15V4M8 8l4-4 4 4" stroke="currentColor"
            strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round"/>
      <path d="M4 16v1.5A2.5 2.5 0 006.5 20h11a2.5 2.5 0 002.5-2.5V16"
            stroke="currentColor" strokeWidth="1.75" strokeLinecap="round"/>
    </svg>
  )
}

function ErrorSvg({ className = '' }: { className?: string }) {
  return (
    <svg viewBox="0 0 16 16" fill="none" className={className}
         xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
      <circle cx="8" cy="8" r="6.5" stroke="currentColor" strokeWidth="1.3"/>
      <path d="M8 5v4M8 10.5v.5" stroke="currentColor"
            strokeWidth="1.5" strokeLinecap="round"/>
    </svg>
  )
}
