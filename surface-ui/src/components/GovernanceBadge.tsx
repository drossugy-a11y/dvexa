import { getGovernanceTheme } from '../theme/governance-states'

interface Props {
  strategy?: string
  decision?: string
}

export default function GovernanceBadge({ strategy, decision }: Props) {
  if (!strategy) return null

  const theme = getGovernanceTheme(strategy)

  return (
    <span
      className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-medium border"
      style={{
        backgroundColor: theme.badgeBg,
        color: theme.badgeText,
        borderColor: theme.badgeBorder,
        boxShadow: theme.glow !== 'none' ? theme.glow : undefined,
      }}
    >
      <span>{strategy}</span>
      {decision && <span className="opacity-60">→ {decision}</span>}
    </span>
  )
}
