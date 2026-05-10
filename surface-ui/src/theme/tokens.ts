/* Raw Design Tokens — 原始设计令牌，不包含语义映射 */

export const color = {
  /* Background */
  bg: {
    primary: '#0F1115',
    secondary: '#151922',
    tertiary: '#1B2130',
    elevated: '#1E2638',
    overlay: 'rgba(0, 0, 0, 0.6)',
  },
  /* Border */
  border: {
    primary: '#252B36',
    soft: '#2F3744',
    focus: '#7C9EFF',
  },
  /* Text */
  text: {
    primary: '#E6EAF2',
    secondary: '#9AA4B2',
    muted: '#6B7280',
    inverse: '#0F1115',
  },
  /* Accent */
  accent: {
    primary: '#7C9EFF',
    blue: '#38BDF8',
    purple: '#A78BFA',
    green: '#4ADE80',
    yellow: '#FBBF24',
    red: '#F87171',
    orange: '#FB923C',
    cyan: '#22D3EE',
  },
  /* Semantic */
  semantic: {
    success: '#4ADE80',
    warning: '#FBBF24',
    danger: '#F87171',
    info: '#38BDF8',
    optimization: '#A78BFA',
  },
} as const

export const spacing = {
  xs: 4,
  sm: 8,
  md: 12,
  lg: 16,
  xl: 24,
  xxl: 32,
} as const

export const radius = {
  sm: 4,
  md: 6,
  lg: 8,
  xl: 12,
  full: 9999,
} as const

export const fontSize = {
  xs: 10,
  sm: 12,
  md: 13,
  lg: 15,
  xl: 18,
  xxl: 24,
} as const

export const fontWeight = {
  normal: 400,
  medium: 500,
  semibold: 600,
  bold: 700,
} as const

export const zIndex = {
  base: 0,
  dropdown: 50,
  sticky: 60,
  drawer: 100,
  modal: 200,
  toast: 300,
} as const

export const animation = {
  duration: {
    fast: 120,
    normal: 150,
    slow: 200,
  },
  easing: 'ease-out',
} as const

export const breakpoint = {
  mobile: 767,
  desktop: 768,
} as const

export const touch = {
  minSize: 44,
} as const
