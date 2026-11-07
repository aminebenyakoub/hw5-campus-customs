import { useEffect, useRef, type ReactNode } from 'react'
import { agentMeta, formatArgs, outputText, plain } from '../agents'
import type { AuditEvent } from '../types'

function preview(result: unknown): string {
  const s = typeof result === 'string' ? result : JSON.stringify(result)
  return s.length > 160 ? s.slice(0, 160) + '…' : s
}

function Row({ e }: { e: AuditEvent }) {
  const meta = agentMeta(e.agent)
  const d = e.detail
  let body: ReactNode = null
  let kind = e.event as string

  switch (e.event) {
    case 'agent_start':
      body = <><b>{meta.label}</b> picked up: <span className="muted">{String(d.task)}</span></>
      break
    case 'model_response':
      if (!d.text) return null // tool calls get their own rows
      body = <span className="said">{plain(String(d.text))}</span>
      kind = 'said'
      break
    case 'tool_call':
      if (d.tool === 'final_result') return null
      body = <code className="tool">{String(d.tool)}({formatArgs(d.args)})</code>
      break
    case 'tool_result':
      body = <code className="result">↳ {preview(d.result ?? d.retry)}</code>
      break
    case 'delegation':
      body = d.accepted ? (
        <><b>{meta.label}</b> <span className="arrow">→</span> <b>{agentMeta(String(d.to)).label}</b>: {String(d.task)}</>
      ) : (
        <><b>{meta.label}</b> tried {agentMeta(String(d.to)).label}: <span className="muted">{String(d.refusal)}</span></>
      )
      break
    case 'agent_end':
      body = <><b>{meta.label}</b> finished: {outputText(d.output)}</>
      break
    case 'agent_error':
      body = <><b>{meta.label}</b> error: {String(d.error)}</>
      break
  }

  return (
    <li className={`row row--${kind} agent--${e.agent}`} style={{ marginLeft: e.depth * 18 }}>
      <span className="row__who" title={meta.label}>{meta.glyph}</span>
      <div className="row__body">{body}</div>
      <time className="row__time">{e.ts.slice(11, 19)}</time>
    </li>
  )
}

export function Timeline({ events, running }: { events: AuditEvent[]; running: boolean }) {
  const box = useRef<HTMLDivElement>(null)
  // Follow new events inside the log only; never scroll the whole page.
  useEffect(() => {
    const el = box.current
    if (running && el) el.scrollTo({ top: el.scrollHeight, behavior: 'smooth' })
  }, [events.length, running])

  if (!events.length) return <p className="empty">No agent activity yet. Run the agents to watch them work.</p>
  return (
    <div className="timeline" ref={box}>
      <ol>{events.map(e => <Row key={e.index} e={e} />)}</ol>
    </div>
  )
}
