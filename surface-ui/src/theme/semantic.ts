/* Semantic Color System — 语义颜色映射

将 raw tokens 映射到具体的 UI 语义。
所有组件应该引用这个文件，而不是直接引用 tokens。
*/

import { color } from './tokens'

export const surface = {
  /* 背景层级 */
  main: color.bg.primary,
  panel: color.bg.secondary,
  raised: color.bg.tertiary,
  elevated: color.bg.elevated,
  overlay: color.bg.overlay,

  /* 交互状态 */
  hover: 'rgba(124, 158, 255, 0.06)',
  active: 'rgba(124, 158, 255, 0.12)',
  selected: 'rgba(124, 158, 255, 0.15)',
} as const

export const border = {
  default: color.border.primary,
  soft: color.border.soft,
  focus: color.border.focus,
  error: color.semantic.danger,
  success: color.semantic.success,
  warning: color.semantic.warning,
} as const

export const text = {
  primary: color.text.primary,
  secondary: color.text.secondary,
  muted: color.text.muted,
  /* 语义文字 */
  success: color.semantic.success,
  warning: color.semantic.warning,
  danger: color.semantic.danger,
  info: color.semantic.info,
  link: color.accent.primary,
} as const

export const icon = {
  primary: color.text.secondary,
  muted: color.text.muted,
  success: color.semantic.success,
  warning: color.semantic.warning,
  danger: color.semantic.danger,
  info: color.semantic.info,
} as const
