import type { Config } from 'tailwindcss'

const config: Config = {
  content: [
    './index.html',
    './src/**/*.{ts,tsx}',
  ],
  theme: {
    extend: {
      colors: {
        // ── Official DravyaSense brand palette ────────────────
        brand: {
          mint:   '#F4F6F0',   // Alabaster Mint  — primary background (60%)
          forest: '#1C2A22',   // Dark Forest     — text / structure   (30%)
          sage:   '#D2DCDB',   // Silver Sage     — accents / borders  (10%)
          white:  '#FFFFFF',   // White           — content surfaces
        },

        // ── Derived semantic tokens ───────────────────────────
        // Surface hierarchy (light theme)
        surface: {
          base:    '#F4F6F0',  // page background
          raised:  '#FFFFFF',  // cards / panels
          overlay: '#EEF1EB',  // subtle inset surfaces
          border:  '#D2DCDB',  // all borders / dividers
        },

        // Text hierarchy
        text: {
          primary:   '#1C2A22',  // headings, body
          secondary: '#4A5E50',  // supporting copy
          muted:     '#8A9E90',  // captions, metadata
          inverse:   '#F4F6F0',  // text on dark surfaces
        },

        // Forest tones for depth
        forest: {
          950: '#0E1912',
          900: '#1C2A22',
          800: '#263830',
          700: '#32493F',
          600: '#4A5E50',
        },

        // Sage tones
        sage: {
          100: '#EEF1EB',
          200: '#E2E8E0',
          300: '#D2DCDB',
          400: '#B5C3C2',
          500: '#8A9E90',
        },
      },

      fontFamily: {
        // Serif for editorial headings — falls back gracefully
        serif: ['"Playfair Display"', 'Georgia', 'serif'],
        sans:  ['Inter', 'system-ui', 'sans-serif'],
        mono:  ['"JetBrains Mono"', '"Fira Code"', 'monospace'],
      },

      fontSize: {
        // Editorial scale
        'display-2xl': ['4.5rem',  { lineHeight: '1.1',  letterSpacing: '-0.03em' }],
        'display-xl':  ['3.75rem', { lineHeight: '1.1',  letterSpacing: '-0.025em' }],
        'display-lg':  ['3rem',    { lineHeight: '1.15', letterSpacing: '-0.02em' }],
        'display-md':  ['2.25rem', { lineHeight: '1.2',  letterSpacing: '-0.02em' }],
        'display-sm':  ['1.875rem',{ lineHeight: '1.25', letterSpacing: '-0.015em' }],
      },

      spacing: {
        section: '7rem',
        'section-sm': '4rem',
      },

      borderRadius: {
        none: '0',
        sm:   '0.25rem',
        md:   '0.375rem',
        DEFAULT: '0.5rem',
        lg:   '0.75rem',
        xl:   '1rem',
        '2xl': '1.5rem',
        full: '9999px',
      },

      boxShadow: {
        card:   '0 1px 3px 0 rgba(28,42,34,0.06), 0 1px 2px -1px rgba(28,42,34,0.04)',
        'card-hover': '0 4px 16px 0 rgba(28,42,34,0.10), 0 2px 4px -1px rgba(28,42,34,0.06)',
        btn:    '0 1px 2px 0 rgba(28,42,34,0.08)',
        section: '0 0 0 1px rgba(210,220,219,0.8)',
      },

      transitionTimingFunction: {
        editorial: 'cubic-bezier(0.25, 0.46, 0.45, 0.94)',
      },

      animation: {
        'fade-up':    'fadeUp 0.6s cubic-bezier(0.25,0.46,0.45,0.94) both',
        'fade-in':    'fadeIn 0.5s ease both',
        'draw-line':  'drawLine 1.2s ease forwards',
      },

      keyframes: {
        fadeUp: {
          from: { opacity: '0', transform: 'translateY(24px)' },
          to:   { opacity: '1', transform: 'translateY(0)' },
        },
        fadeIn: {
          from: { opacity: '0' },
          to:   { opacity: '1' },
        },
        drawLine: {
          from: { strokeDashoffset: '1000' },
          to:   { strokeDashoffset: '0' },
        },
      },
    },
  },
  plugins: [],
}

export default config
