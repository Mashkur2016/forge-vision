import type { Config } from 'tailwindcss'

export default {
  darkMode: 'class',
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        // Light mode palette (UIDesign.md)
        primary: {
          DEFAULT: '#2563EB',
          hover: '#1D4ED8',
        },
        surface: {
          DEFAULT: '#F8FAFC',
          2: '#F1F5F9',
        },
        // Semantic
        success: '#16A34A',
        warning: '#D97706',
        error: '#DC2626',
        info: '#0284C7',
        // Text
        'text-primary': '#0F172A',
        'text-secondary': '#64748B',
        'text-muted': '#94A3B8',
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
      },
      borderRadius: {
        card: '12px',
        button: '8px',
        input: '6px',
        badge: '20px',
      },
      boxShadow: {
        card: '0 1px 3px rgba(0,0,0,0.08), 0 1px 2px rgba(0,0,0,0.04)',
        'card-dark': '0 1px 3px rgba(0,0,0,0.4), 0 1px 2px rgba(0,0,0,0.3)',
      },
    },
  },
  plugins: [],
} satisfies Config
