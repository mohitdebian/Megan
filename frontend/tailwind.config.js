/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        megan: {
          bg: '#08080c',
          surface: '#0c0c14',
          panel: '#111118',
          border: '#1a1a24',
          'border-bright': '#252530',
          ring: '#22d3ee',
          cyan: '#22d3ee',
          amber: '#f59e0b',
          green: '#34d399',
          rose: '#fb7185',
          text: '#e2e2e8',
          'text-dim': '#5a5a6a',
          'text-muted': '#3a3a4e',
          slate: '#64748b',
          white: '#ffffff',
        },
      },
      fontFamily: {
        mono: ['"Share Tech Mono"', '"JetBrains Mono"', 'monospace'],
        sans: ['"Share Tech Mono"', 'monospace'],
      },
      animation: {
        'fade-in': 'fade-in 0.3s ease-out',
        'slide-up': 'slide-up 0.3s ease-out',
        'spin-slow': 'spin-slow 8s linear infinite',
        'ring-pulse': 'ring-pulse 2.5s ease-in-out infinite',
        'ring-spin': 'ring-spin 3s linear infinite',
        'cursor-blink': 'cursor-blink 1s step-end infinite',
        'orb-breathe': 'orb-breathe 3s ease-in-out infinite',
        'holo-scan': 'holo-scan 5s linear infinite',
      },
      keyframes: {
        'fade-in': {
          from: { opacity: '0' },
          to: { opacity: '1' },
        },
        'slide-up': {
          from: { opacity: '0', transform: 'translateY(8px)' },
          to: { opacity: '1', transform: 'translateY(0)' },
        },
        'spin-slow': {
          from: { transform: 'rotate(0deg)' },
          to: { transform: 'rotate(360deg)' },
        },
        'ring-pulse': {
          '0%, 100%': { opacity: '0.4', transform: 'scale(1)' },
          '50%': { opacity: '0.8', transform: 'scale(1.05)' },
        },
        'ring-spin': {
          from: { transform: 'rotate(0deg)' },
          to: { transform: 'rotate(360deg)' },
        },
        'cursor-blink': {
          '0%, 100%': { opacity: '1' },
          '50%': { opacity: '0' },
        },
        'orb-breathe': {
          '0%, 100%': { transform: 'scale(1)', opacity: '0.9' },
          '50%': { transform: 'scale(1.08)', opacity: '1' },
        },
        'holo-scan': {
          '0%': { transform: 'translateY(-100%)' },
          '100%': { transform: 'translateY(100%)' },
        },
      },
    },
  },
  plugins: [],
}
