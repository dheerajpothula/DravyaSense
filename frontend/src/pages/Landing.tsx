import { useEffect, useState } from 'react'

type HealthStatus = 'checking' | 'ok' | 'error'

interface HealthResponse {
  status: string
  service: string
  version: string
}

/**
 * Landing page — DravyaSense project entry point.
 * Displays the application identity and verifies backend connectivity.
 */
export default function Landing() {
  const [healthStatus, setHealthStatus] = useState<HealthStatus>('checking')
  const [healthData, setHealthData] = useState<HealthResponse | null>(null)

  useEffect(() => {
    fetch('/api/health')
      .then((res) => res.json())
      .then((data: HealthResponse) => {
        setHealthData(data)
        setHealthStatus('ok')
      })
      .catch(() => {
        setHealthStatus('error')
      })
  }, [])

  return (
    <main className="min-h-screen bg-surface-950 flex flex-col items-center justify-center px-6">
      {/* ── Logo mark ─────────────────────────────────────────── */}
      <div className="mb-6 flex items-center gap-3">
        <div className="w-10 h-10 rounded-xl bg-teal-500 flex items-center justify-center shadow-lg shadow-teal-500/30">
          <span className="text-surface-950 font-bold text-lg select-none">DS</span>
        </div>
        <span className="text-ink-400 text-sm font-mono tracking-widest uppercase">
          Electronic Tongue Analytics
        </span>
      </div>

      {/* ── Application title ─────────────────────────────────── */}
      <h1 className="text-5xl font-bold tracking-tight mb-4 text-center">
        <span className="text-gradient-teal">DravyaSense</span>
      </h1>

      <p className="text-ink-200 text-lg text-center max-w-xl leading-relaxed mb-2">
        PCA and t-SNE visualization of electronic-tongue sensor data
        for herbal category separation.
      </p>
      <p className="text-ink-400 text-sm text-center max-w-lg mb-10">
        Upload your sensor dataset, configure preprocessing, and explore
        dimensionality-reduced representations — no labels required.
      </p>

      {/* ── Module overview pills ─────────────────────────────── */}
      <div className="flex flex-wrap gap-2 justify-center mb-12 max-w-2xl">
        {[
          'Dataset Management',
          'Preprocessing Studio',
          'PCA Analysis',
          't-SNE Analysis',
          'PCA vs t-SNE',
          'Category Separation',
          'Experiment History',
          'Research Insights',
        ].map((module) => (
          <span
            key={module}
            className="px-3 py-1 rounded-full text-xs font-medium bg-surface-800 text-ink-200 border border-surface-600"
          >
            {module}
          </span>
        ))}
      </div>

      {/* ── Backend health indicator ──────────────────────────── */}
      <div className="w-full max-w-sm bg-surface-800 border border-surface-600 rounded-xl p-4">
        <div className="flex items-center justify-between mb-2">
          <span className="text-xs text-ink-400 font-mono uppercase tracking-widest">
            Backend Status
          </span>
          <StatusBadge status={healthStatus} />
        </div>

        {healthStatus === 'ok' && healthData && (
          <div className="mt-3 space-y-1">
            <HealthRow label="Service" value={healthData.service} />
            <HealthRow label="Version" value={healthData.version} />
            <HealthRow label="Response" value={healthData.status} />
          </div>
        )}

        {healthStatus === 'error' && (
          <p className="mt-2 text-xs text-red-400">
            Cannot reach backend at{' '}
            <code className="font-mono">localhost:8000</code>. Start the
            FastAPI server and refresh.
          </p>
        )}

        {healthStatus === 'checking' && (
          <p className="mt-2 text-xs text-ink-400 animate-pulse">
            Connecting to backend…
          </p>
        )}
      </div>

      <p className="mt-8 text-ink-600 text-xs text-center">
        Development build — Day 1 scaffold · DravyaSense v0.1.0
      </p>
    </main>
  )
}

/* ── Sub-components ───────────────────────────────────────────── */

function StatusBadge({ status }: { status: HealthStatus }) {
  if (status === 'checking') {
    return (
      <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-medium bg-surface-700 text-ink-400">
        <span className="w-1.5 h-1.5 rounded-full bg-ink-400 animate-pulse" />
        Checking
      </span>
    )
  }
  if (status === 'ok') {
    return (
      <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-medium bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
        <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" />
        Online
      </span>
    )
  }
  return (
    <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-medium bg-red-500/10 text-red-400 border border-red-500/20">
      <span className="w-1.5 h-1.5 rounded-full bg-red-400" />
      Offline
    </span>
  )
}

function HealthRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between items-center">
      <span className="text-xs text-ink-400">{label}</span>
      <span className="text-xs font-mono text-ink-200">{value}</span>
    </div>
  )
}
