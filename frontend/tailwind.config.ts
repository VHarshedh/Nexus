import type { Config } from 'tailwindcss';

const config: Config = {
  content: ['./src/**/*.{js,ts,jsx,tsx,mdx}'],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        nexus: {
          bg: '#0a0a0f',
          surface: '#12121a',
          'surface-2': '#1a1a26',
          border: '#2a2a3a',
          accent: '#6366f1',
          'accent-hover': '#818cf8',
          'accent-muted': '#4f46e5',
          success: '#22c55e',
          warning: '#f59e0b',
          danger: '#ef4444',
          text: '#e2e8f0',
          'text-muted': '#94a3b8',
          'text-dim': '#64748b',
        },
      },
      animation: {
        'pulse-slow': 'pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite',
        'slide-up': 'slideUp 0.3s ease-out',
        'fade-in': 'fadeIn 0.2s ease-out',
      },
      keyframes: {
        slideUp: {
          '0%': { transform: 'translateY(10px)', opacity: '0' },
          '100%': { transform: 'translateY(0)', opacity: '1' },
        },
        fadeIn: {
          '0%': { opacity: '0' },
          '100%': { opacity: '1' },
        },
      },
    },
  },
  plugins: [],
};

export default config;
