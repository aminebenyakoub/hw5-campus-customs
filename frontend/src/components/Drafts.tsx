import { agentMeta } from '../agents'
import type { Draft } from '../types'

export function Drafts({ drafts }: { drafts: Draft[] }) {
  if (!drafts.length) return null
  return (
    <div className="drafts">
      {drafts.map(d => (
        <article key={d.id} className="letter">
          <div className="letter__stamp">Draft · not sent</div>
          <div className="letter__to">To: <b>{d.recipient}</b></div>
          <div className="letter__subject">{d.subject}</div>
          <p className="letter__body">{d.body}</p>
          <div className="muted small">Written by {agentMeta(d.written_by).label}</div>
        </article>
      ))}
    </div>
  )
}
