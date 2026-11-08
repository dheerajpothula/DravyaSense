import { useRef } from 'react'
import { Link } from 'react-router-dom'
import BotanicalIllustration from '../components/BotanicalIllustration'

/* ─────────────────────────────────────────────────────────────────
   DravyaSense Landing Page
   Brand: Alabaster Mint · Dark Forest · Silver Sage · White
   Typography: Playfair Display (headings) · Inter (body)
───────────────────────────────────────────────────────────────── */

export default function Landing() {
  const methodologyRef = useRef<HTMLElement>(null)
  const researchRef    = useRef<HTMLElement>(null)
  const aboutRef       = useRef<HTMLElement>(null)

  const scrollTo = (ref: React.RefObject<HTMLElement | null>) => {
    ref.current?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }

  return (
    <div className="min-h-screen bg-brand-mint text-text-primary">

      {/* ════════════════════════════════════════════════════════
          NAV
      ════════════════════════════════════════════════════════ */}
      <header className="sticky top-0 z-50 bg-brand-mint/95 backdrop-blur-sm border-b border-surface-border">
        <div className="container-editorial">
          <nav className="flex items-center justify-between h-16">

            {/* Logo */}
            <Link to="/" className="flex items-center gap-3 group">
              <div className="w-8 h-8 bg-forest-900 flex items-center justify-center rounded-sm
                              group-hover:bg-forest-800 transition-colors duration-200">
                <span className="text-text-inverse text-xs font-bold tracking-wider select-none">DS</span>
              </div>
              <div className="flex flex-col leading-none">
                <span className="text-sm font-semibold text-text-primary tracking-tight">DravyaSense</span>
                <span className="text-[10px] text-text-muted tracking-[0.12em] uppercase">Research Platform</span>
              </div>
            </Link>

            {/* Desktop navigation */}
            <ul className="hidden md:flex items-center gap-8">
              {[
                { label: 'Home',        action: () => window.scrollTo({ top: 0, behavior: 'smooth' }) },
                { label: 'Research',    action: () => scrollTo(researchRef) },
                { label: 'Methodology', action: () => scrollTo(methodologyRef) },
                { label: 'About',       action: () => scrollTo(aboutRef) },
              ].map(({ label, action }) => (
                <li key={label}>
                  <button
                    onClick={action}
                    className="text-sm text-text-secondary hover:text-text-primary
                               link-underline transition-colors duration-200 cursor-pointer
                               bg-transparent border-none p-0"
                  >
                    {label}
                  </button>
                </li>
              ))}
            </ul>

            {/* CTA */}
            <Link to="/dashboard" className="btn-nav hidden md:inline-flex">
              Explore Platform
              <ArrowRight className="w-3.5 h-3.5" />
            </Link>

            {/* Mobile hamburger placeholder */}
            <button className="md:hidden p-2 text-text-secondary hover:text-text-primary"
                    aria-label="Open menu">
              <MenuIcon />
            </button>
          </nav>
        </div>
      </header>


      {/* ════════════════════════════════════════════════════════
          HERO
      ════════════════════════════════════════════════════════ */}
      <section className="container-editorial pt-20 pb-section">
        <div className="grid lg:grid-cols-2 gap-16 items-center">

          {/* Left — Text */}
          <div className="animate-fade-up">
            <p className="eyebrow mb-6">
              <span className="w-6 h-px bg-text-muted inline-block" />
              Electronic Tongue Intelligence
            </p>

            <h1 className="font-serif text-display-lg text-text-primary mb-6 leading-[1.1]">
              Decoding Herbal{' '}
              <em className="not-italic text-forest-700">
                Identity
              </em>{' '}
              Through Sensor Data
            </h1>

            <p className="text-text-secondary text-lg leading-relaxed max-w-lg mb-10">
              DravyaSense applies unsupervised dimensionality reduction — PCA and
              t-SNE — to multi-channel electronic-tongue sensor readings, revealing
              whether traditional herbal categories produce distinguishable patterns
              without relying on labels.
            </p>

            <div className="flex flex-wrap gap-4">
              <Link to="/dashboard" className="btn-primary">
                Explore Platform
                <ArrowRight className="w-4 h-4" />
              </Link>
              <button
                onClick={() => scrollTo(methodologyRef)}
                className="btn-secondary"
              >
                View Methodology
              </button>
            </div>

            {/* Metadata strip */}
            <div className="flex items-center gap-6 mt-12 pt-8 border-t border-surface-border">
              <MetaStat label="Algorithm" value="PCA + t-SNE" />
              <div className="v-rule" />
              <MetaStat label="Domain" value="Herbal Science" />
              <div className="v-rule" />
              <MetaStat label="Approach" value="Unsupervised ML" />
            </div>
          </div>

          {/* Right — Botanical illustration */}
          <div className="animate-fade-up delay-200 relative">
            <div className="relative rounded-sm overflow-hidden shadow-card-hover
                            border border-surface-border">
              <BotanicalIllustration className="w-full h-auto" />

              {/* Illustration disclaimer */}
              <div className="absolute bottom-0 left-0 right-0
                              bg-brand-white/95 backdrop-blur-sm
                              border-t border-surface-border px-4 py-2.5
                              flex items-center justify-between gap-4">
                <p className="text-[10px] text-text-muted font-mono tracking-wide leading-relaxed">
                  Conceptual illustration — not derived from experimental data.
                  Leaf motifs represent herbal samples; scatter nodes represent
                  sensor readings in reduced-dimensional space.
                </p>
                <span className="shrink-0 inline-flex items-center px-2 py-0.5 text-[9px]
                                 font-medium tracking-wider uppercase rounded-sm
                                 bg-sage-200 text-forest-800 border border-sage-400">
                  Illustrative
                </span>
              </div>
            </div>

            {/* Decorative rule */}
            <div className="absolute -top-4 -right-4 w-24 h-24 border border-sage-300
                            rounded-sm -z-10 hidden lg:block" />
          </div>
        </div>
      </section>


      {/* ════════════════════════════════════════════════════════
          DIVIDER
      ════════════════════════════════════════════════════════ */}
      <div className="container-editorial">
        <div className="divider" />
      </div>


      {/* ════════════════════════════════════════════════════════
          RESEARCH INTRODUCTION
      ════════════════════════════════════════════════════════ */}
      <section ref={researchRef} className="container-editorial py-section scroll-mt-20">
        <div className="grid lg:grid-cols-12 gap-12">

          {/* Left label column */}
          <div className="lg:col-span-3">
            <p className="eyebrow sticky top-24">
              <span className="w-6 h-px bg-text-muted inline-block" />
              Research Context
            </p>
          </div>

          {/* Right content column */}
          <div className="lg:col-span-9">
            <h2 className="font-serif text-display-md text-text-primary mb-8 leading-tight">
              Can an electronic tongue distinguish between herbal traditions?
            </h2>

            <div className="grid md:grid-cols-2 gap-x-12 gap-y-6 text-text-secondary
                            text-base leading-relaxed">
              <p>
                Electronic tongues use arrays of electrochemical sensors to generate
                multi-dimensional taste profiles. Each sensor responds differently to
                dissolved compounds, producing a high-dimensional fingerprint unique
                to each sample.
              </p>
              <p>
                The challenge is visibility. Raw sensor data is difficult to interpret
                directly. Dimensionality reduction techniques like PCA and t-SNE
                compress this complexity into two or three dimensions — making
                patterns legible without discarding the underlying science.
              </p>
              <p>
                DravyaSense provides a rigorous, reproducible workflow: upload your
                dataset, configure preprocessing, run PCA and t-SNE with full
                parameter control, and evaluate how cleanly herbal categories
                cluster — all without imposing labels onto the model.
              </p>
              <p>
                Separation metrics (silhouette score, Davies-Bouldin index) are
                computed on request. They quantify clustering quality honestly —
                flagged clearly as label-assisted evaluation, not unsupervised proof.
              </p>
            </div>

            {/* Label-exclusion notice */}
            <div className="mt-8 flex items-start gap-3 px-5 py-4
                            border border-sage-300 bg-sage-100/60">
              <svg viewBox="0 0 12 12" fill="none" className="w-3.5 h-3.5 shrink-0 mt-0.5
                   text-forest-800" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
                <path d="M1 1h4.5L11 6.5 6.5 11 1 5.5V1z" stroke="currentColor"
                      strokeWidth="1.2" strokeLinejoin="round"/>
                <circle cx="3.5" cy="3.5" r="0.75" fill="currentColor"/>
              </svg>
              <p className="text-sm text-forest-800 leading-relaxed">
                <span className="font-semibold">Category labels are never inputs to PCA or t-SNE.</span>
                {' '}Both algorithms fit on sensor feature columns only. Labels are
                carried as metadata throughout the pipeline and used exclusively
                for post-analysis evaluation — when you choose to assess how well
                known categories cluster in the resulting embedding.
              </p>
            </div>

            {/* Highlight callout */}
            <div className="mt-10 p-8 bg-surface-overlay border-l-2 border-forest-900">
              <p className="font-serif text-xl text-text-primary leading-relaxed">
                "No fabricated results. No synthetic visualizations.
                Every chart and metric is derived from data you upload."
              </p>
              <p className="mt-3 text-sm text-text-muted">DravyaSense design principle</p>
            </div>
          </div>
        </div>
      </section>


      {/* ════════════════════════════════════════════════════════
          DIVIDER
      ════════════════════════════════════════════════════════ */}
      <div className="container-editorial">
        <div className="divider" />
      </div>


      {/* ════════════════════════════════════════════════════════
          METHODOLOGY
      ════════════════════════════════════════════════════════ */}
      <section ref={methodologyRef} id="methodology"
               className="container-editorial py-section scroll-mt-20">

        <div className="mb-14">
          <p className="eyebrow mb-4">
            <span className="w-6 h-px bg-text-muted inline-block" />
            Methodology
          </p>
          <h2 className="font-serif text-display-md text-text-primary max-w-xl leading-tight">
            Five stages from sensor to insight
          </h2>
        </div>

        <div className="space-y-px border border-surface-border">
          {METHODOLOGY_STEPS.map((step, i) => (
            <MethodologyRow key={step.id} step={step} index={i} />
          ))}
        </div>
      </section>


      {/* ════════════════════════════════════════════════════════
          DIVIDER
      ════════════════════════════════════════════════════════ */}
      <div className="container-editorial">
        <div className="divider" />
      </div>


      {/* ════════════════════════════════════════════════════════
          FEATURES
      ════════════════════════════════════════════════════════ */}
      <section className="container-editorial py-section">
        <div className="mb-14">
          <p className="eyebrow mb-4">
            <span className="w-6 h-px bg-text-muted inline-block" />
            Platform Capabilities
          </p>
          <h2 className="font-serif text-display-md text-text-primary max-w-xl leading-tight">
            Every tool a researcher needs
          </h2>
        </div>

        <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-px border border-surface-border
                        bg-surface-border">
          {FEATURES.map((feat) => (
            <FeatureCard key={feat.title} {...feat} />
          ))}
        </div>
      </section>


      {/* ════════════════════════════════════════════════════════
          DIVIDER
      ════════════════════════════════════════════════════════ */}
      <div className="container-editorial">
        <div className="divider" />
      </div>


      {/* ════════════════════════════════════════════════════════
          ABOUT
      ════════════════════════════════════════════════════════ */}
      <section ref={aboutRef} id="about"
               className="container-editorial py-section scroll-mt-20">
        <div className="grid lg:grid-cols-12 gap-12">

          {/* Left label */}
          <div className="lg:col-span-3">
            <p className="eyebrow sticky top-24">
              <span className="w-6 h-px bg-text-muted inline-block" />
              About
            </p>
          </div>

          {/* Right content */}
          <div className="lg:col-span-9">
            <h2 className="font-serif text-display-md text-text-primary mb-8 leading-tight">
              A research tool for herbal science
            </h2>

            <div className="grid md:grid-cols-2 gap-x-12 gap-y-6 text-text-secondary
                            text-base leading-relaxed mb-10">
              <p>
                DravyaSense was developed as part of an investigation into whether
                electronic-tongue technology can reproducibly distinguish between
                traditional Ayurvedic herb categories — <em>Dravya</em> — based on
                taste-profile data alone, without human sensory panels.
              </p>
              <p>
                The platform applies only unsupervised machine learning methods.
                PCA and t-SNE operate entirely on sensor feature columns. Category
                labels, when present, are used exclusively for post-hoc evaluation
                of cluster quality — never to guide the reduction algorithm.
              </p>
              <p>
                The pipeline is designed for full reproducibility. Every experiment
                records its preprocessing configuration, algorithm parameters, and
                random seed. Results can be re-generated at any time from the
                Experiment History module.
              </p>
              <p>
                DravyaSense is an open research build. All source code is version-
                controlled. No result is displayed unless it is computed from data
                you have uploaded in the current session.
              </p>
            </div>

            {/* Technology strip */}
            <div className="border-t border-surface-border pt-8">
              <p className="text-xs text-text-muted tracking-[0.12em] uppercase mb-5">
                Built with
              </p>
              <div className="flex flex-wrap gap-2">
                {[
                  'React 18', 'TypeScript', 'Vite', 'Tailwind CSS', 'Plotly.js',
                  'FastAPI', 'Python 3.13', 'scikit-learn', 'pandas', 'SQLite',
                ].map((tech) => (
                  <span key={tech}
                        className="px-3 py-1 text-xs font-medium text-text-secondary
                                   border border-surface-border bg-surface-raised
                                   rounded-sm font-mono">
                    {tech}
                  </span>
                ))}
              </div>
            </div>
          </div>
        </div>
      </section>


      {/* ════════════════════════════════════════════════════════
          DIVIDER
      ════════════════════════════════════════════════════════ */}
      <div className="container-editorial">
        <div className="divider" />
      </div>


      {/* ════════════════════════════════════════════════════════
          CTA BAND
      ════════════════════════════════════════════════════════ */}
      <section className="bg-forest-900 text-text-inverse">
        <div className="container-editorial py-section-sm">
          <div className="flex flex-col md:flex-row items-start md:items-center
                          justify-between gap-8">
            <div>
              <h2 className="font-serif text-display-sm text-text-inverse mb-3">
                Ready to analyse your dataset?
              </h2>
              <p className="text-sage-300 text-base max-w-md">
                Upload your electronic-tongue sensor CSV, configure the pipeline,
                and visualize the results in minutes.
              </p>
            </div>
            <div className="flex gap-4 shrink-0">
              <Link to="/dashboard"
                    className="inline-flex items-center gap-2 px-6 py-3 bg-brand-mint
                               text-forest-900 text-sm font-medium rounded-sm
                               hover:bg-sage-100 transition-colors duration-200">
                Explore Platform
                <ArrowRight className="w-4 h-4" />
              </Link>
              <button
                onClick={() => scrollTo(methodologyRef)}
                className="inline-flex items-center gap-2 px-6 py-3 border border-sage-500/50
                           text-sage-200 text-sm font-medium rounded-sm
                           hover:border-sage-300 hover:text-text-inverse
                           transition-colors duration-200"
              >
                View Methodology
              </button>
            </div>
          </div>
        </div>
      </section>


      {/* ════════════════════════════════════════════════════════
          FOOTER
      ════════════════════════════════════════════════════════ */}
      <footer className="bg-brand-mint border-t border-surface-border">
        <div className="container-editorial py-12">

          <div className="grid md:grid-cols-3 gap-10 mb-12">

            {/* Brand */}
            <div>
              <div className="flex items-center gap-3 mb-4">
                <div className="w-7 h-7 bg-forest-900 flex items-center justify-center rounded-sm">
                  <span className="text-text-inverse text-[10px] font-bold tracking-wider">DS</span>
                </div>
                <span className="text-sm font-semibold text-text-primary">DravyaSense</span>
              </div>
              <p className="text-text-muted text-sm leading-relaxed max-w-xs">
                PCA and t-SNE visualization of electronic-tongue sensor data
                for herbal category separation.
              </p>
            </div>

            {/* Research */}
            <div>
              <p className="text-xs font-medium tracking-[0.12em] uppercase text-text-muted mb-4">
                Platform
              </p>
              <ul className="space-y-2">
                {['Dataset Management', 'Preprocessing Studio',
                  'PCA Analysis', 't-SNE Analysis', 'Experiment History'].map((item) => (
                  <li key={item}>
                    <Link to="/dashboard"
                          className="text-sm text-text-secondary hover:text-text-primary
                                     link-underline transition-colors duration-200">
                      {item}
                    </Link>
                  </li>
                ))}
              </ul>
            </div>

            {/* Science */}
            <div>
              <p className="text-xs font-medium tracking-[0.12em] uppercase text-text-muted mb-4">
                Algorithms
              </p>
              <ul className="space-y-2">
                {['Principal Component Analysis', 't-Distributed Stochastic Neighbor Embedding',
                  'Silhouette Score', 'Davies-Bouldin Index', 'StandardScaler · RobustScaler'].map((item) => (
                  <li key={item}>
                    <span className="text-sm text-text-secondary">{item}</span>
                  </li>
                ))}
              </ul>
            </div>
          </div>

          <div className="divider mb-6" />

          <div className="flex flex-col md:flex-row items-start md:items-center
                          justify-between gap-4">
            <p className="text-xs text-text-muted">
              DravyaSense · Electronic Tongue Intelligence Platform · Research Build v0.1.0
            </p>
            <p className="text-xs text-text-muted">
              Unsupervised ML · All visualizations derived from uploaded data only
            </p>
          </div>
        </div>
      </footer>

    </div>
  )
}


/* ═══════════════════════════════════════════════════════════════
   DATA
═══════════════════════════════════════════════════════════════ */

const METHODOLOGY_STEPS = [
  {
    id: '01',
    title:    'Electronic-Tongue Sensor Readings',
    subtitle: 'Multi-channel electrochemical measurement',
    body:     'Arrays of potentiometric or voltammetric sensors produce a high-dimensional response vector for each sample. Each channel responds to different dissolved taste compounds — sourness, bitterness, astringency, saltiness, sweetness — creating a unique chemical fingerprint.',
  },
  {
    id: '02',
    title:    'Data Preprocessing',
    subtitle: 'Normalization, imputation, outlier handling',
    body:     'Raw sensor readings are screened for missing values and outliers. Scaling strategies (StandardScaler, MinMaxScaler, RobustScaler) are applied to the sensor feature matrix only. Sample identifiers and category labels are excluded from the feature space and preserved as metadata.',
  },
  {
    id: '03',
    title:    'Principal Component Analysis',
    subtitle: 'Linear dimensionality reduction',
    body:     'PCA projects the preprocessed sensor matrix into orthogonal components ordered by explained variance. Component loadings reveal which sensors drive the most variance. The first two or three components are visualized as interactive scatter plots, colored optionally by category label.',
  },
  {
    id: '04',
    title:    't-Distributed Stochastic Neighbor Embedding',
    subtitle: 'Non-linear manifold exploration',
    body:     't-SNE preserves local neighborhood structure when compressing to 2D or 3D. Perplexity, learning rate, and iteration count are fully configurable. A fixed random seed ensures reproducibility. The algorithm may run on the raw preprocessed data or on PCA-reduced components for efficiency.',
  },
  {
    id: '05',
    title:    'Category Separation Evaluation',
    subtitle: 'Silhouette score · Davies-Bouldin index',
    body:     'When category labels are provided, quantitative separation metrics are computed on the embedding coordinates. Results are explicitly labeled as "label-assisted evaluation" — they measure how well known categories cluster in the reduced space, not unsupervised discovery.',
  },
]

interface Feature {
  number: string
  title:  string
  body:   string
}

const FEATURES: Feature[] = [
  {
    number: '01',
    title:  'Dataset Management',
    body:   'Upload CSV or Excel sensor files. Automatic column detection classifies sensor channels, sample identifiers, and category labels. Raw data is never modified.',
  },
  {
    number: '02',
    title:  'Preprocessing Studio',
    body:   'Configure scaling strategy, missing-value handling, and outlier detection. Preview the effect on your data distribution before committing to any transformation.',
  },
  {
    number: '03',
    title:  'PCA Analysis',
    body:   'Interactive 2D and 3D scatter plots, explained variance bar chart, and component loadings heatmap. Configurable number of components.',
  },
  {
    number: '04',
    title:  't-SNE Analysis',
    body:   'Full parameter panel: perplexity, learning rate, iterations, random seed. Run on raw data or PCA pre-reduction. Reproducible by design.',
  },
  {
    number: '05',
    title:  'Side-by-Side Comparison',
    body:   'PCA and t-SNE visualizations synchronized in one view. Identical color coding and category assignment across both projections.',
  },
  {
    number: '06',
    title:  'Experiment History',
    body:   'Every analysis run is stored with its full parameter configuration. Re-run, compare, or export any past experiment as a structured report.',
  },
]


/* ═══════════════════════════════════════════════════════════════
   SUB-COMPONENTS
═══════════════════════════════════════════════════════════════ */

function MetaStat({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="text-[10px] text-text-muted tracking-[0.12em] uppercase mb-0.5">{label}</p>
      <p className="text-sm font-medium text-text-primary">{value}</p>
    </div>
  )
}

interface Step {
  id:       string
  title:    string
  subtitle: string
  body:     string
}

function MethodologyRow({ step, index }: { step: Step; index: number }) {
  return (
    <div className={`grid md:grid-cols-12 gap-0 bg-surface-raised border-b border-surface-border
                     group hover:bg-surface-overlay transition-colors duration-200
                     ${index === 0 ? 'border-t' : ''}`}>

      {/* Step number */}
      <div className="md:col-span-1 flex items-start justify-center pt-8 pb-8 border-r border-surface-border">
        <span className="font-mono text-xs text-text-muted">{step.id}</span>
      </div>

      {/* Title column */}
      <div className="md:col-span-3 px-8 py-8 border-r border-surface-border">
        <h3 className="font-serif text-lg text-text-primary leading-snug mb-1">
          {step.title}
        </h3>
        <p className="text-xs text-text-muted tracking-wide">{step.subtitle}</p>
      </div>

      {/* Body column */}
      <div className="md:col-span-8 px-8 py-8">
        <p className="text-text-secondary text-sm leading-relaxed max-w-xl">
          {step.body}
        </p>
      </div>
    </div>
  )
}

function FeatureCard({ number, title, body }: Feature) {
  return (
    <div className="bg-surface-raised p-8 hover:bg-surface-overlay
                    transition-colors duration-200 group">
      <p className="font-mono text-xs text-text-muted mb-5">{number}</p>
      <h3 className="font-serif text-lg text-text-primary mb-3 leading-snug
                     group-hover:text-forest-800 transition-colors duration-200">
        {title}
      </h3>
      <p className="text-sm text-text-secondary leading-relaxed">{body}</p>
    </div>
  )
}

/* ── Minimal inline SVG icons ─────────────────────────────────── */

function ArrowRight({ className = '' }: { className?: string }) {
  return (
    <svg viewBox="0 0 16 16" fill="none" className={className}
         xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
      <path d="M3 8h10M9 4l4 4-4 4" stroke="currentColor"
            strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
    </svg>
  )
}

function MenuIcon({ className = '' }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" className={`w-5 h-5 ${className}`}
         xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
      <path d="M4 6h16M4 12h16M4 18h16" stroke="currentColor"
            strokeWidth="1.5" strokeLinecap="round"/>
    </svg>
  )
}
