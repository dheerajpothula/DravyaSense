import { useState } from 'react'
import { Link, Outlet, useLocation, useNavigate } from 'react-router-dom'

/**
 * Dashboard — Application workspace shell.
 *
 * Layout: full-viewport, collapsible left sidebar + scrollable main content.
 * No fake data. All modules show their true build status.
 * Upload action is locked until the Dataset module is implemented.
 */

/* ─────────────────────────────────────────────────────────────────
   Module registry
   status values:
     'available'     — implemented and usable
     'in-development'— being built in the current sprint
     'planned'       — designed but not yet started
───────────────────────────────────────────────────────────────── */
type ModuleStatus = 'available' | 'in-development' | 'planned'

interface Module {
  id:     string
  label:  string
  desc:   string
  status: ModuleStatus
  path:   string
  group:  'data' | 'analysis' | 'evaluation' | 'reporting'
}

const MODULES: Module[] = [
  {
    id: '01', label: 'Dataset Management',
    desc:   'Upload CSV/Excel sensor files, inspect schema, tag column types.',
    status: 'available', path: '/dashboard/datasets', group: 'data',
  },
  {
    id: '02', label: 'Data Explorer',
    desc:   'Preview raw data, descriptive statistics, distribution plots.',
    status: 'available', path: '/dashboard/explorer', group: 'data',
  },
  {
    id: '03', label: 'Preprocessing Studio',
    desc:   'Configure scaling, imputation and outlier handling per experiment.',
    status: 'available', path: '/dashboard/preprocess', group: 'data',
  },
  {
    id: '04', label: 'PCA Analysis',
    desc:   'Run PCA, inspect explained variance, component loadings and scatter.',
    status: 'available', path: '/dashboard/pca', group: 'analysis',
  },
  {
    id: '05', label: 't-SNE Analysis',
    desc:   'Configure perplexity, learning rate and seed; explore 2D/3D embeddings.',
    status: 'available', path: '/dashboard/tsne', group: 'analysis',
  },
  {
    id: '06', label: 'PCA vs t-SNE',
    desc:   'Side-by-side synchronized comparison of both projections.',
    status: 'planned', path: '/dashboard/compare', group: 'analysis',
  },
  {
    id: '07', label: 'Category Separation',
    desc:   'Silhouette score, Davies-Bouldin index — label-assisted evaluation only.',
    status: 'planned', path: '/dashboard/evaluation', group: 'evaluation',
  },
  {
    id: '08', label: 'Experiment History',
    desc:   'Browse, re-run and compare all past analysis experiments.',
    status: 'planned', path: '/dashboard/history', group: 'reporting',
  },
  {
    id: '09', label: 'Research Insights',
    desc:   'Automated narrative summary of experiment findings.',
    status: 'planned', path: '/dashboard/insights', group: 'reporting',
  },
  {
    id: '10', label: 'Settings',
    desc:   'Platform preferences, default parameters, data retention.',
    status: 'planned', path: '/dashboard/settings', group: 'reporting',
  },
]

const NAV_GROUPS: { key: Module['group']; label: string }[] = [
  { key: 'data',       label: 'Data' },
  { key: 'analysis',   label: 'Analysis' },
  { key: 'evaluation', label: 'Evaluation' },
  { key: 'reporting',  label: 'Reporting' },
]

/* ─────────────────────────────────────────────────────────────────
   Component
───────────────────────────────────────────────────────────────── */
export default function Dashboard() {
  const [sidebarOpen, setSidebarOpen] = useState(true)
  const location = useLocation()
  const navigate = useNavigate()

  const activePath = location.pathname

  return (
    <div className="min-h-screen bg-brand-mint text-text-primary flex flex-col">

      {/* ════════════════════════════════════════════════════════
          TOP BAR
      ════════════════════════════════════════════════════════ */}
      <header className="sticky top-0 z-40 bg-brand-white border-b border-surface-border h-12 flex items-center shrink-0">
        <div className="w-full flex items-center px-4 gap-4">

          {/* Sidebar toggle */}
          <button
            onClick={() => setSidebarOpen((v) => !v)}
            className="p-1.5 rounded-sm hover:bg-surface-overlay transition-colors duration-150
                       text-text-muted hover:text-text-primary"
            aria-label={sidebarOpen ? 'Collapse sidebar' : 'Expand sidebar'}
          >
            <SidebarIcon className="w-4 h-4" />
          </button>

          {/* Vertical rule */}
          <div className="w-px h-5 bg-surface-border" />

          {/* Brand + breadcrumb */}
          <div className="flex items-center gap-2.5">
            <button
              onClick={() => navigate('/dashboard')}
              className="flex items-center gap-2 hover:opacity-80 transition-opacity"
            >
              <div className="w-6 h-6 bg-forest-900 flex items-center justify-center rounded-sm shrink-0">
                <span className="text-text-inverse text-[9px] font-bold tracking-wider select-none">DS</span>
              </div>
              <span className="text-sm font-semibold text-text-primary">DravyaSense</span>
            </button>
            {activePath !== '/dashboard' && activePath !== '/dashboard/' && (
              <>
                <span className="text-text-muted text-sm select-none">/</span>
                <span className="text-sm text-text-muted">
                  {MODULES.find((m) => activePath.startsWith(m.path))?.label ?? 'Module'}
                </span>
              </>
            )}
          </div>

          {/* Spacer */}
          <div className="flex-1" />

          {/* Back to site */}
          <Link
            to="/"
            className="inline-flex items-center gap-1.5 text-xs text-text-muted
                       hover:text-text-primary transition-colors duration-200"
          >
            <ArrowLeft className="w-3 h-3" />
            Back to Site
          </Link>
        </div>
      </header>


      {/* ════════════════════════════════════════════════════════
          BODY — sidebar + content
      ════════════════════════════════════════════════════════ */}
      <div className="flex flex-1 overflow-hidden">

        {/* ── Sidebar ────────────────────────────────────────── */}
        <aside
          className={`
            shrink-0 bg-brand-white border-r border-surface-border
            flex flex-col overflow-y-auto overflow-x-hidden
            transition-all duration-200 ease-in-out
            ${sidebarOpen ? 'w-56' : 'w-0 border-r-0'}
          `}
          aria-hidden={!sidebarOpen}
        >
          {/* Inner — hidden via overflow when width = 0 */}
          <div className="min-w-[14rem] flex flex-col flex-1 py-4">

            {/* Overview link */}
            <div className="mb-4 px-2">
              <button
                onClick={() => navigate('/dashboard')}
                className={[
                  'w-full flex items-center gap-2.5 px-2 py-1.5 text-sm rounded-sm',
                  'transition-colors duration-150',
                  activePath === '/dashboard' || activePath === '/dashboard/'
                    ? 'bg-surface-overlay text-text-primary font-medium'
                    : 'text-text-secondary hover:bg-surface-overlay hover:text-text-primary',
                ].join(' ')}
              >
                <HomeIcon className="w-3.5 h-3.5 shrink-0" />
                <span>Overview</span>
              </button>
            </div>

            {/* Nav groups */}
            {NAV_GROUPS.map((group) => {
              const items = MODULES.filter((m) => m.group === group.key)
              return (
                <div key={group.key} className="mb-4">
                  <p className="px-4 mb-1 text-[10px] font-medium tracking-[0.12em]
                                uppercase text-text-muted">
                    {group.label}
                  </p>
                  {items.map((mod) => (
                    <SidebarItem
                      key={mod.id}
                      mod={mod}
                      isActive={activePath.startsWith(mod.path)}
                      onClick={() => {
                        if (mod.status === 'available') navigate(mod.path)
                      }}
                    />
                  ))}
                </div>
              )
            })}

            {/* Spacer + version */}
            <div className="mt-auto px-4 pt-4 border-t border-surface-border">
              <p className="text-[10px] text-text-muted font-mono">v0.1.0 · Research Build</p>
            </div>
          </div>
        </aside>

        {/* ── Main content ───────────────────────────────────── */}
        <main className="flex-1 overflow-y-auto">
          <div className="px-8 lg:px-12 xl:px-16 py-10">
            <Outlet />
          </div>
        </main>
      </div>

      {/* ════════════════════════════════════════════════════════
          STATUS BAR
      ════════════════════════════════════════════════════════ */}
      <footer className="shrink-0 h-8 bg-brand-white border-t border-surface-border
                         flex items-center px-5 gap-4">
        <span className="text-[10px] text-text-muted font-mono">
          DravyaSense Platform · v0.1.0
        </span>
        <div className="w-px h-3 bg-surface-border" />
        <span className="text-[10px] text-text-muted">
          Unsupervised ML · All results derived from uploaded data
        </span>
      </footer>

    </div>
  )
}


/* ─────────────────────────────────────────────────────────────────
   DashboardHome — rendered at /dashboard (the Outlet default)
───────────────────────────────────────────────────────────────── */
export function DashboardHome() {
  const navigate = useNavigate()
  return (
    <div className="flex flex-col gap-8">
      {/* Page header */}
      <div className="pb-6 border-b border-surface-border">
        <p className="eyebrow mb-3">
          <span className="w-5 h-px bg-text-muted inline-block" />
          Research Workspace
        </p>
        <h1 className="font-serif text-display-sm text-text-primary mb-3 leading-tight">
          Electronic-Tongue Analytics
        </h1>
        <p className="text-text-secondary text-sm leading-relaxed max-w-xl">
          Upload your sensor dataset to begin. Modules unlock sequentially —
          preprocessing requires a loaded dataset, analysis requires preprocessed
          data, and evaluation requires a completed embedding run.
        </p>
      </div>

      {/* Build status notice */}
      <div className="flex items-start gap-3 px-5 py-4
                      bg-surface-overlay border border-surface-border rounded-sm">
        <InfoIcon className="w-4 h-4 text-text-muted shrink-0 mt-0.5" />
        <p className="text-sm text-text-secondary leading-relaxed">
          <span className="font-medium text-text-primary">Dataset Management and Data Explorer are now available.</span>
          {' '}All other modules are designed and planned.
        </p>
      </div>

      {/* Module grid */}
      <div>
        <h2 className="font-serif text-lg text-text-primary mb-5">Module Status</h2>
        <div className="flex flex-wrap gap-4 mb-6">
          <LegendItem status="available"      label="Available" />
          <LegendItem status="in-development" label="In Development" />
          <LegendItem status="planned"        label="Planned" />
        </div>
        <div className="grid sm:grid-cols-2 xl:grid-cols-3 gap-3">
          {MODULES.map((mod) => (
            <ModuleCard key={mod.id} mod={mod} onNavigate={() => {
              if (mod.status === 'available') navigate(mod.path)
            }} />
          ))}
        </div>
      </div>

      {/* Quick start */}
      <div className="border border-surface-border bg-brand-white">
        <div className="px-8 py-6 border-b border-surface-border">
          <h2 className="font-serif text-lg text-text-primary">Get Started</h2>
        </div>
        <div className="px-8 py-6 flex items-start gap-5">
          <div className="w-9 h-9 bg-forest-900 rounded-sm flex items-center
                          justify-center shrink-0 mt-0.5">
            <UploadIcon className="w-4 h-4 text-text-inverse" />
          </div>
          <div>
            <h3 className="font-medium text-text-primary mb-1.5">
              Step 1 — Upload your sensor dataset
            </h3>
            <p className="text-text-secondary text-sm leading-relaxed mb-4 max-w-lg">
              Prepare a CSV or Excel file with one row per sample. Sensor channels
              go in numeric columns. Sample IDs and category labels are detected
              automatically and never enter the feature matrix.
            </p>
            <button
              onClick={() => navigate('/dashboard/datasets')}
              className="inline-flex items-center gap-2 px-4 py-2 text-sm font-medium
                         bg-forest-900 text-text-inverse rounded-sm
                         hover:bg-forest-800 transition-colors duration-200"
            >
              <UploadIcon className="w-3.5 h-3.5" />
              Open Dataset Management
            </button>
          </div>
        </div>
      </div>

      {/* Pipeline */}
      <div>
        <h2 className="font-serif text-lg text-text-primary mb-5">Analysis Pipeline</h2>
        <p className="text-sm text-text-secondary mb-6 max-w-xl">
          Category labels are never inputs to PCA or t-SNE — they are carried as
          metadata and used only for post-analysis evaluation.
        </p>
        <div className="border border-surface-border bg-brand-white overflow-hidden">
          {PIPELINE_STAGES.map((stage, i) => (
            <PipelineRow key={stage.label} stage={stage}
                         isLast={i === PIPELINE_STAGES.length - 1} />
          ))}
        </div>
      </div>
    </div>
  )
}


/* ─────────────────────────────────────────────────────────────────
   Data
───────────────────────────────────────────────────────────────── */
const PIPELINE_STAGES = [
  {
    step:  '01',
    label: 'Upload Dataset',
    note:  'CSV / Excel sensor readings. Sample IDs and category labels detected and isolated as metadata.',
    labelNote: null,
  },
  {
    step:  '02',
    label: 'Preprocessing',
    note:  'Scaling (Standard / MinMax / Robust), missing-value imputation, outlier detection — applied to sensor features only.',
    labelNote: null,
  },
  {
    step:  '03',
    label: 'PCA',
    note:  'Fitted on the preprocessed sensor feature matrix. Category labels are not passed to the algorithm.',
    labelNote: 'Labels excluded from fit',
  },
  {
    step:  '04',
    label: 't-SNE',
    note:  'Runs on preprocessed features or PCA output. Fully configurable seed for reproducibility.',
    labelNote: 'Labels excluded from fit',
  },
  {
    step:  '05',
    label: 'Evaluation',
    note:  'Silhouette score and Davies-Bouldin index computed on embedding coordinates.',
    labelNote: 'Labels used here only — post-analysis evaluation',
  },
]


/* ─────────────────────────────────────────────────────────────────
   Sub-components
───────────────────────────────────────────────────────────────── */

function SidebarItem({ mod, isActive, onClick }: { mod: Module; isActive: boolean; onClick: () => void }) {
  const dot: Record<ModuleStatus, string> = {
    'available':       'bg-forest-700',
    'in-development':  'bg-sage-400',
    'planned':         'bg-surface-border',
  }
  const canNavigate = mod.status === 'available'

  return (
    <div
      role={canNavigate ? 'button' : undefined}
      tabIndex={canNavigate ? 0 : -1}
      onClick={onClick}
      onKeyDown={(e) => { if ((e.key === 'Enter' || e.key === ' ') && canNavigate) onClick() }}
      className={[
        'flex items-center gap-2.5 px-4 py-1.5 text-sm transition-colors duration-150',
        canNavigate ? 'cursor-pointer' : 'cursor-default',
        isActive
          ? 'bg-surface-overlay text-text-primary font-medium'
          : canNavigate
            ? 'text-text-secondary hover:bg-surface-overlay hover:text-text-primary'
            : 'text-text-muted',
      ].join(' ')}
    >
      <span className={`w-1.5 h-1.5 rounded-full shrink-0 ${dot[mod.status]}`} />
      <span className="truncate">{mod.label}</span>
    </div>
  )
}

function ModuleCard({ mod, onNavigate }: { mod: Module; onNavigate?: () => void }) {
  const clickable = mod.status === 'available' && onNavigate
  return (
    <div
      role={clickable ? 'button' : undefined}
      tabIndex={clickable ? 0 : -1}
      onClick={clickable ? onNavigate : undefined}
      onKeyDown={(e) => { if ((e.key === 'Enter' || e.key === ' ') && clickable) onNavigate?.() }}
      className={[
        'bg-brand-white border border-surface-border p-6 flex flex-col gap-3',
        clickable ? 'cursor-pointer hover:shadow-card-hover hover:border-forest-900/20 transition-all duration-200' : '',
      ].join(' ')}
    >
      <div className="flex items-start justify-between gap-2">
        <span className="font-mono text-[10px] text-text-muted">{mod.id}</span>
        <StatusPill status={mod.status} />
      </div>
      <div>
        <p className="text-sm font-medium text-text-primary leading-snug mb-1">
          {mod.label}
        </p>
        <p className="text-xs text-text-muted leading-relaxed">{mod.desc}</p>
      </div>
    </div>
  )
}

function StatusPill({ status }: { status: ModuleStatus }) {
  const styles: Record<ModuleStatus, string> = {
    'available': `bg-forest-900/[0.07] text-forest-900 border-forest-900/20`,
    'in-development': `bg-sage-200 text-forest-800 border-sage-400`,
    'planned': `bg-surface-overlay text-text-muted border-surface-border`,
  }
  const labels: Record<ModuleStatus, string> = {
    'available':      'Available',
    'in-development': 'In Development',
    'planned':        'Planned',
  }
  return (
    <span className={`inline-flex items-center px-2 py-0.5 text-[10px] font-medium
                      tracking-wide uppercase rounded-sm border shrink-0 ${styles[status]}`}>
      {labels[status]}
    </span>
  )
}

function LegendItem({ status, label }: { status: ModuleStatus; label: string }) {
  return (
    <div className="flex items-center gap-2">
      <StatusPill status={status} />
      <span className="text-xs text-text-muted">{label}</span>
    </div>
  )
}

interface PipelineStage {
  step:      string
  label:     string
  note:      string
  labelNote: string | null
}

function PipelineRow({
  stage, isLast,
}: { stage: PipelineStage; isLast: boolean }) {
  return (
    <div className={`flex items-start gap-0 ${isLast ? '' : 'border-b border-surface-border'}`}>
      {/* Step number */}
      <div className="w-14 shrink-0 flex items-start justify-center py-5 border-r border-surface-border">
        <span className="font-mono text-xs text-text-muted">{stage.step}</span>
      </div>

      {/* Label */}
      <div className="w-36 shrink-0 px-5 py-5 border-r border-surface-border">
        <span className="text-sm font-medium text-text-primary">{stage.label}</span>
      </div>

      {/* Note */}
      <div className="flex-1 px-5 py-5 flex flex-wrap items-start gap-3">
        <p className="text-sm text-text-secondary leading-relaxed flex-1 min-w-0">
          {stage.note}
        </p>
        {stage.labelNote && (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-1 text-[10px]
                           font-medium tracking-wide rounded-sm shrink-0
                           bg-sage-200 text-forest-800 border border-sage-400">
            <TagIcon className="w-2.5 h-2.5" />
            {stage.labelNote}
          </span>
        )}
      </div>
    </div>
  )
}


/* ─────────────────────────────────────────────────────────────────
   Icons
───────────────────────────────────────────────────────────────── */
function SidebarIcon({ className = '' }: { className?: string }) {
  return (
    <svg viewBox="0 0 16 16" fill="none" className={className}
         xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
      <rect x="1" y="1" width="14" height="14" rx="1.5"
            stroke="currentColor" strokeWidth="1.3"/>
      <line x1="5.5" y1="1" x2="5.5" y2="15"
            stroke="currentColor" strokeWidth="1.3"/>
    </svg>
  )
}

function HomeIcon({ className = '' }: { className?: string }) {
  return (
    <svg viewBox="0 0 16 16" fill="none" className={className}
         xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
      <path d="M2 7l6-5 6 5v7H10v-4H6v4H2V7z" stroke="currentColor"
            strokeWidth="1.3" strokeLinejoin="round"/>
    </svg>
  )
}

function ArrowLeft({ className = '' }: { className?: string }) {
  return (
    <svg viewBox="0 0 16 16" fill="none" className={className}
         xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
      <path d="M13 8H3M7 12l-4-4 4-4" stroke="currentColor"
            strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
    </svg>
  )
}

function UploadIcon({ className = '' }: { className?: string }) {
  return (
    <svg viewBox="0 0 16 16" fill="none" className={className}
         xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
      <path d="M8 10V3M5 6l3-3 3 3M3 11v1.5A1.5 1.5 0 004.5 14h7a1.5 1.5 0 001.5-1.5V11"
            stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
    </svg>
  )
}

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

function TagIcon({ className = '' }: { className?: string }) {
  return (
    <svg viewBox="0 0 12 12" fill="none" className={className}
         xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
      <path d="M1 1h4.5L11 6.5 6.5 11 1 5.5V1z" stroke="currentColor"
            strokeWidth="1.2" strokeLinejoin="round"/>
      <circle cx="3.5" cy="3.5" r="0.75" fill="currentColor"/>
    </svg>
  )
}
