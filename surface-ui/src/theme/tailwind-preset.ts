/* Tailwind CSS Preset — 将 Design Tokens 映射为 Tailwind 类 */

import type { Config } from 'tailwindcss'

const preset: Partial<Config> = {
  theme: {
    extend: {
      colors: {
        surface: {
          900: '#0F1115',
          850: '#151922',
          800: '#1B2130',
          750: '#1E2638',
          700: '#252B36',
          600: '#2F3744',
          500: '#3F4756',
        },
        text: {
          primary: '#E6EAF2',
          secondary: '#9AA4B2',
          muted: '#6B7280',
        },
        accent: {
          primary: '#7C9EFF',
          blue: '#38BDF8',
          purple: '#A78BFA',
          green: '#4ADE80',
          yellow: '#FBBF24',
          red: '#F87171',
          orange: '#FB923C',
          cyan: '#22D3EE',
          600: '#7C9EFF',
          500: '#8AABFF',
        },
        semantic: {
          success: '#4ADE80',
          warning: '#FBBF24',
          danger: '#F87171',
          info: '#38BDF8',
          optimization: '#A78BFA',
        },
        runtime: {
          planning: '#38BDF8',
          governance: '#A78BFA',
          tool: '#4ADE80',
          memory: '#FBBF24',
          complete: '#4ADE80',
          error: '#F87171',
          optimization: '#A78BFA',
          drift: '#FB923C',
        },
      },
      borderColor: {
        DEFAULT: '#252B36',
        soft: '#2F3744',
      },
      maxWidth: {
        chat: '720px',
      },
      spacing: {
        touch: '44px',
      },
      screens: {
        mobile: { max: '767px' },
        desktop: { min: '768px' },
      },
      animation: {
        'pulse-subtle': 'pulse-subtle 2s ease-in-out infinite',
        'shimmer': 'shimmer 2s ease-in-out infinite',
        'stream-pulse': 'stream-pulse 1.5s ease-in-out infinite',
      },
      keyframes: {
        'pulse-subtle': {
          '0%, 100%': { opacity: '0.6' },
          '50%': { opacity: '1' },
        },
        'shimmer': {
          '0%': { opacity: '0.3' },
          '50%': { opacity: '0.6' },
          '100%': { opacity: '0.3' },
        },
        'stream-pulse': {
          '0%, 100%': { opacity: '0.7' },
          '50%': { opacity: '1' },
        },
      },
      transitionDuration: {
        fast: '120ms',
        normal: '150ms',
        slow: '200ms',
      },
      transitionTimingFunction: {
        'ease-out': 'ease-out',
      },
    },
  },
}

export default preset
