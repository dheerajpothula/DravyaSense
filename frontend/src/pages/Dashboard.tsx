import { Link } from 'react-router-dom'

/**
 * Dashboard — Application workspace entry point.
 *
 * This is the platform shell that all analysis modules will live inside.
 * Currently shows a clean empty state while modules are being built.
 * No fake data, no placeholder charts.
 */

const UPCOMING_MODULES = [
  { id: '01', label: 'Dataset Management',     status: 'next',     path: '/dashboard/datasets' },
  { id: '02', label: 'Preprocessing Studio',   status: 'upcoming', path: '/dashboard/preprocess' },
  { id: '03', label: 'PCA Analysis',           status: 'upcoming', path: '/dashboard/pca' },
  { id: '04', label: 't-SNE Analysis',         status: 'upcoming', path: '/dashboard/tsne' },
  { id: '05', label: 'PCA vs t-SNE',           status: 'upcoming', path: '/dashboard/compare' },
  { id: '06', label: 'Category Separation',    status: 'upcoming', path: '/dashboard/evaluation' },
  { id: '07', label: 'Experiment History',     status: 'upcoming', path: '/dashboard/history' },
  { id: '08', label: 'Research Insights',      status: 'upcoming', path: '/dashboard/insights' },
] as const

type ModuleStatus = 'next' | 'upcoming'

export default function Dashboard() {
  return (
    <div className="min-h-screen bg-brand-mint text-text-primary flex flex-col">

      {/* ── Top bar ─────────────────────────────────────────── */}
      <header className="bg-brand-white border-b border-surface-border">
        <div className="container-editorial">
          <div className="flex items-center justify-between h-14">

            {/* Brand */}
            <div className="flex items-center gap-3">
              <div className="w-7 h-7 bg-forest-900 flex items-center justify-center rounded-sm">
                <span className="text-text-inverse text-[10px] font-bold tracking-wider">DS</span>
              </div>
              <div className="flex items-baseline gap-2">
                <span className="text-sm font-semibold text-text-primary">DravyaSense</span>
                <span className="text-xs text-text-muted">/ Platform</span>
              </div>
            </div>

            {/* Back to site */}
            <Link
              to="/"
              className="inline-flex items-center gap-2 text-sm text-text-secondary
                         hover:text-text-primary transition-colors duration-200"
            >
              <ArrowLeft className="w-3.5 h-3.5" />
              Back to Site
            </Link>
          </div>
        </div>
      </header>

      {/* ── Main content ─────────────────────────────────────── */}
      <main className="flex-1 container-editorial py-16">

        {/* Page heading */}
        <div className="mb-14 max-w-xl">
          <p className="eyebrow mb-4">
            <span className="w-6 h-px bg-text-muted inline-block" />
            Research Workspace
          </p>
          <h1 className="font-serif text-display-md text-text-primary mb-4 leading-tight">
            Electronic-Tongue Analytics
          </h1>
          <p className="text-text-secondary text-base leading-relaxed">
            Upload your sensor dataset to begin. Each module becomes available
            after the previous step is complete — from raw data upload through
            PCA, t-SNE, and category separation evaluation.
          </p>
        </div>

        {/* ── Module grid ───────────────────────────────────── */}
        <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-px border border-surface-border
                        bg-surface-border mb-14">
          {UPCOMING_MODULES.map((mod) => (
            <ModuleCard key={mod.id} {...mod} />
          ))}
        </div>

        {/* ── Getting started callout ───────────────────────── */}
        <div className="border border-surface-border bg-brand-white p-10 max-w-2xl">
          <div className="flex items-start gap-6">
            <div className="w-10 h-10 bg-forest-900 rounded-sm flex items-center
                            justify-center shrink-0 mt-0.5">
              <UploadIcon className="w-4 h-4 text-text-inverse" />
            </div>
            <div>
              <h2 className="font-serif text-xl text-text-primary mb-2">
                Start with your dataset
              </h2>
              <p className="text-text-secondary text-sm leading-relaxed mb-5">
                Upload a CSV or Excel file containing your electronic-tongue sensor
                readings. The platform will automatically detect sensor columns,
                sample identifiers, and category labels — keeping labels strictly
                separate from the feature matrix.
              </p>
              <div className="flex gap-3">
                <button
                  disabled
                  className="inline-flex items-center gap-2 px-5 py-2.5 bg-forest-900
                             text-text-inverse text-sm font-medium rounded-sm
                             opacity-40 cursor-not-allowed"
                  title="Dataset module coming in Day 2"
                >
                  Upload Dataset
                  <ArrowRight className="w-3.5 h-3.5" />
                </button>
                <span className="inline-flex items-center px-3 py-2 text-xs text-text-muted
                                 border border-surface-border rounded-sm font-mono">
                  Module in development
                </span>
              </div>
            </div>
          </div>
        </div>

        {/* ── Pipeline overview ─────────────────────────────── */}
        <div className="mt-14">
          <p className="eyebrow mb-8">
            <span className="w-6 h-px bg-text-muted inline-block" />
            Analysis Pipeline
          </p>

          <div className="flex flex-col md:flex-row items-start md:items-center gap-0
                          border border-surface-border bg-brand-white overflow-hidden">
            {PIPELINE_STEPS.map((step, i) => (
              <div key={step.label}
                   className="flex-1 flex items-center gap-3 px-6 py-5
                              border-b md:border-b-0 md:border-r border-surface-border last:border-0">
                <span className="font-mono text-xs text-text-muted shrink-0">{String(i + 1).padStart(2, '0')}</span>
                <div className="w-px h-6 bg-surface-border shrink-0" />
                <span className="text-sm text-text-secondary">{step.label}</span>
              </div>
            ))}
          </div>
        </div>

      </main>

      {/* ── Footer strip ─────────────────────────────────────── */}
      <footer className="border-t border-surface-border bg-brand-white">
        <div className="container-editorial py-4">
          <div className="flex items-center justify-between">
            <p className="text-xs text-text-muted">
              DravyaSense Platform · Research Build v0.1.0
            </p>
            <p className="text-xs text-text-muted font-mono">
              Unsupervised ML · No fabricated results
            </p>
          </div>
        </div>
      </footer>
    </div>
  )
}

/* ── Sub-components ─────────────────────────────────────────── */

function ModuleCard({
  id, label, status,
}: { id: string; label: string; status: ModuleStatus; path: string }) {
  return (
    <div className="bg-brand-white p-6 flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <span className="font-mono text-xs text-text-muted">{id}</span>
        <StatusPill status={status} />
      </div>
      <p className="text-sm font-medium text-text-primary leading-snug">{label}</p>
    </div>
  )
}

function StatusPill({ status }: { status: ModuleStatus }) {
  if (status === 'next') {
    return (
      <span className="inline-flex items-center gap-1 px-2 py-0.5 text-[10px] font-medium
                       tracking-wide uppercase rounded-sm bg-forest-900/8 text-forest-900
                       border border-forest-900/20">
        <span className="w-1 h-1 rounded-full bg-forest-900 inline-block" />
        Next
      </span>
    )
  }
  return (
    <span className="inline-flex items-center px-2 py-0.5 text-[10px] font-medium
                     tracking-wide uppercase rounded-sm bg-surface-overlay text-text-muted
                     border border-surface-border">
      Upcoming
    </span>
  )
}

const PIPELINE_STEPS = [
  { label: 'Upload Dataset' },
  { label: 'Preprocessing' },
  { label: 'PCA' },
  { label: 't-SNE' },
  { label: 'Evaluation' },
]

/* ── Icons ──────────────────────────────────────────────────── */

function ArrowLeft({ className = '' }: { className?: string }) {
  return (
    <svg viewBox="0 0 16 16" fill="none" className={className}
         xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
      <path d="M13 8H3M7 12l-4-4 4-4" stroke="currentColor"
            strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  )
}

function ArrowRight({ className = '' }: { className?: string }) {
  return (
    <svg viewBox="0 0 16 16" fill="none" className={className}
         xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
      <path d="M3 8h10M9 4l4 4-4 4" stroke="currentColor"
            strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  )
}

function UploadIcon({ className = '' }: { className?: string }) {
  return (
    <svg viewBox="0 0 16 16" fill="none" className={className}
         xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
      <path d="M8 10V3M5 6l3-3 3 3M3 11v1.5A1.5 1.5 0 004.5 14h7a1.5 1.5 0 001.5-1.5V11"
            stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  )
}
