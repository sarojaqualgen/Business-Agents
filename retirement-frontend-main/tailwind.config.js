/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        // Professional banking theme — white surfaces, soft gray cards,
        // orange primary accent (ICICI / Capital One inspired).
        bg: {
          DEFAULT: '#F6F7F9',
          surface: '#FFFFFF',
          s2: '#F1F3F6',
          s3: '#E9ECF1',
        },
        border: {
          DEFAULT: '#E5E8EF',
          strong: '#D4D9E3',
        },
        text: {
          DEFAULT: '#151B2C',
          muted: '#5B6478',
          faint: '#9AA2B4',
        },
        accent: {
          DEFAULT: '#F97316',
          dark: '#C2410C',
          light: '#FFEDD9',
        },
        success: '#15803D',
        warning: '#B45309',
        danger: '#DC2626',
        purple: '#6D28D9',
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', '-apple-system', 'Segoe UI', 'sans-serif'],
        mono: ['ui-monospace', 'SF Mono', 'Menlo', 'monospace'],
      },
      borderRadius: {
        card: '16px',
      },
      boxShadow: {
        card: '0 1px 2px rgba(16,24,40,0.04), 0 1px 3px rgba(16,24,40,0.06)',
        'card-hover': '0 4px 10px rgba(16,24,40,0.06), 0 2px 4px rgba(16,24,40,0.05)',
      },
    },
  },
  plugins: [],
};
