import { AGENTS, activityOf, agentMeta, outputText, plain } from '../agents'
import type { AgentName, AuditEvent } from '../types'

interface Props {
  events: AuditEvent[]
  running: boolean
}

/** Five desks. The agent that is working glows; each shows what it is doing and its latest words. */
export function AgentFloor({ events, running }: Props) {
  const last = (name: AgentName) => [...events].reverse().find(e => e.agent === name)
  const said = (name: AgentName) => {
    for (let i = events.length - 1; i >= 0; i--) {
      const e = events[i]
      if (e.agent !== name) continue
      if (e.event === 'agent_end') return outputText(e.detail.output)
      if (e.event === 'model_response' && e.detail.text) return plain(String(e.detail.text))
      if (e.event === 'agent_start') return String(e.detail.task ?? '')
    }
    return ''
  }
  const calledBy = (name: AgentName) => {
    const start = events.find(e => e.agent === name && e.event === 'agent_start')
    return start && start.chain.length > 1 ? agentMeta(start.chain[start.chain.length - 2]).label : null
  }
  const latest = events[events.length - 1]

  return (
    <div className="floor">
      {AGENTS.map(a => {
        const e = last(a.name)
        const involved = Boolean(e)
        const done = e?.event === 'agent_end'
        const live = running && involved && !done
        const speaking = running && latest?.agent === a.name
        const words = said(a.name)
        const from = calledBy(a.name)
        return (
          <div
            key={a.name}
            className={`desk desk--${a.name} ${a.name === 'boss' ? 'desk--lead' : ''} ${live ? 'is-live' : ''} ${speaking ? 'is-speaking' : ''} ${!involved ? 'is-idle' : ''}`}
          >
            <div className="desk__head">
              <span className="avatar" aria-hidden>{a.glyph}</span>
              <span>
                <span className="desk__name">{a.label}</span>
                <span className="desk__role">{a.role}</span>
              </span>
            </div>
            <div className="desk__status">
              {live && <span className="dot" />}
              {involved ? activityOf(e) : running ? 'Not needed so far' : 'Not called'}
              {from && <span className="desk__from">via {from}</span>}
            </div>
            {words && <p className="bubble">{words.length > 220 ? words.slice(0, 220) + '…' : words}</p>}
          </div>
        )
      })}
    </div>
  )
}
