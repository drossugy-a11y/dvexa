interface Props {
  status: string
  label?: string
}

const colorMap: Record<string, string> = {
  stable: 'bg-accent-green',
  healthy: 'bg-accent-green',
  full: 'bg-accent-green',
  degraded: 'bg-accent-yellow',
  limited: 'bg-accent-yellow',
  unstable: 'bg-accent-red',
  frozen: 'bg-accent-red',
  quarantined: 'bg-accent-red',
  experimental: 'bg-accent-blue',
  unknown: 'bg-gray-500',
}

export default function StatusIndicator({ status, label }: Props) {
  const color = colorMap[status.toLowerCase()] ?? 'bg-gray-500'
  return (
    <span className="inline-flex items-center gap-1.5">
      <span className={`inline-block w-2 h-2 rounded-full ${color}`} />
      <span className="text-sm">{label ?? status}</span>
    </span>
  )
}
