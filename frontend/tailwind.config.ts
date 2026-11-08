import type { Config } from 'tailwindcss'

const config: Config = {
  content: [
    './index.html',
    './src/**/*.{ts,tsx}',
  ],
  theme: {
    extend: {
      colors: {
        // Primary surface palette — dark navy / charcoal
        surface: {
          950: '#060d18',   // deepest background
          900: '#0b1527',   // sidebar / panels
          800: '#111f38',   // card backgrounds
          700: '#162847',   // elevated cards
          600: '#1e3556',   // borders / dividers
        },
        // Accent palette — teal / emerald
        teal: {
          400: '#2dd4bf',
          500: '#14b8a6',
          600: '#0d9488',
        },
        emerald: {
          400: '#34d399',
          500: '#10b981',
          600: '#059669',
        },
        // Text
        ink: {
          100: '#e8f0fe',
          200: '#c5d3e8',
          400: '#7a93b5',
          600: '#4a6080',
        },
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'Fira Code', 'monospace'],
      },
      borderRadius: {
        xl: '0.875rem',
        '2xl': '1.125rem',
      },
    },
  },
  plugins: [],
}

export default config
