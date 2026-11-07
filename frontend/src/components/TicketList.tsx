import type { Run, Ticket } from '../types'

const TYPE_ICON: Record<string, string> = {
  customer_order: '🛍',
  rent_notice: '🏠',
  price_override: '🏷',
}

export const STATUS_LABEL: Record<string, string> = {
  open: 'Open',
  in_progress: 'In progress',
  waiting_approval: 'Needs approval',
  blocked: 'Blocked',
  resolved: 'Resolved',
}

interface Props {
  tickets: Ticket[]
  selected: number | null
  activeRun: Run | null
  onSelect: (id: number) => void
}

export function TicketList({ tickets, selected, activeRun, onSelect }: Props) {
  return (
    <div className="tickets">
      <h2 className="eyebrow">Ticket board</h2>
      {tickets.map(t => {
        const running = activeRun?.ticket_id === t.id
        return (
          <button
            key={t.id}
            className={`ticket ${selected === t.id ? 'is-selected' : ''} ${t.state === 'resolved' ? 'is-resolved' : ''}`}
            onClick={() => onSelect(t.id)}
          >
            <span className="ticket__icon" aria-hidden>{TYPE_ICON[t.type] ?? '📌'}</span>
            <span className="ticket__body">
              <span className="ticket__top">
                <span className="ticket__id">#{t.id}</span>
                <span className="ticket__type">{t.type.replace('_', ' ')}</span>
              </span>
              <span className="ticket__subject">{t.subject}</span>
              <span className="ticket__requester">{t.requester}</span>
            </span>
            <span className={`pill pill--${running ? 'running' : t.status}`}>
              {running ? <><span className="dot" /> Agents working</> : STATUS_LABEL[t.status] ?? t.status}
            </span>
            {t.state === 'resolved' && <span className="stamp">Resolved</span>}
          </button>
        )
      })}
    </div>
  )
}
