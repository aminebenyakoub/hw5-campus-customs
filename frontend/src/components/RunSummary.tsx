import { AGENTS, agentMeta, outputText } from '../agents'
import type { AuditEvent, TicketOutcome } from '../types'

/** One line per agent that took part: tools it used, who it asked, what it concluded. */
export function RunSummary({ events }: { events: AuditEvent[] }) {
  const bossEnd = events.find(e => e.agent === 'boss' && e.event === 'agent_end')
  const outcome = bossEnd?.detail.output as TicketOutcome | undefined
  const tokens = events.reduce((s, e) => s + e.input_tokens + e.output_tokens, 0)
  const model = events.find(e => e.event === 'model_response')?.model

  const people = AGENTS.filter(a => events.some(e => e.agent === a.name)).map(a => {
    const mine = events.filter(e => e.agent === a.name)
    const tools = [...new Set(mine.filter(e => e.event === 'tool_call' && e.detail.tool !== 'final_result').map(e => String(e.detail.tool)))]
    const asked = [...new Set(mine.filter(e => e.event === 'delegation' && e.detail.accepted).map(e => agentMeta(String(e.detail.to)).label))]
    const end = [...mine].reverse().find(e => e.event === 'agent_end')
    return { a, tools, asked, said: end ? outputText(end.detail.output) : '' }
  })

  return (
    <div className="summary">
      {outcome && (
        <div className="verdict">
          <div className="eyebrow">Boss's final call</div>
          <p>{outcome.decision}</p>
          {outcome.next_steps.length > 0 && (
            <ul>{outcome.next_steps.map((s, i) => <li key={i}>{s}</li>)}</ul>
          )}
        </div>
      )}
      <ul className="who-did">
        {people.map(({ a, tools, asked, said }) => (
          <li key={a.name} className={`agent--${a.name}`}>
            <span className="row__who">{a.glyph}</span>
            <div>
              <b>{a.label}</b>
              {asked.length > 0 && <span className="muted"> · asked {asked.join(', ')}</span>}
              <div className="chips">{tools.map(t => <code key={t} className="chip">{t}</code>)}</div>
              {said && a.name !== 'boss' && <p className="muted small">{said.length > 180 ? said.slice(0, 180) + '…' : said}</p>}
            </div>
          </li>
        ))}
      </ul>
      <div className="tokens">
        {model ?? 'gpt-6-luna'} · {tokens.toLocaleString()} tokens · not called:{' '}
        {AGENTS.filter(a => !people.some(p => p.a.name === a.name)).map(a => a.label).join(', ') || 'none'}
      </div>
    </div>
  )
}
