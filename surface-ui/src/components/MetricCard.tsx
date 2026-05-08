import type { ReactNode } from 'react'

interface Props {
  title: string
  value: string | number
  subtitle?: string
  status?: 'green' | 'yellow' | 'red' | 'blue'
  children?: ReactNode
}

const statusColors: Record<string, string> = {
  green: 'border-l-accent-green',
  yellow: 'border-l-accent-yellow',
  red: 'border-l-accent-red',
  blue: 'border-l-accent-blue',
}

export default function MetricCard({ title, value, subtitle, status, children }: Props) {
  const borderColor = statusColors[status ?? 'blue']
  return (
    <div className={`card border-l-4 ${borderColor}`}>
      <div className="card-title">{title}</div>
      <div className="metric-value">{value}</div>
      {subtitle && <div className="text-xs text-gray-500 mt-1">{subtitle}</div>}
      {children}
    </div>
  )
}
