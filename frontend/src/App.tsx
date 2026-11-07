import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { api, API_URL } from './api'
import { money } from './agents'
import { AgentFloor } from './components/AgentFloor'
import { Approvals } from './components/Approvals'
import { CashMeter } from './components/CashMeter'
import { Drafts } from './components/Drafts'
import { RunSummary } from './components/RunSummary'
import { STATUS_LABEL, TicketList } from './components/TicketList'
import { Timeline } from './components/Timeline'
import type { Approval, AuditEvent, Cash, Draft, Health, Run, Ticket } from './types'

interface Toast {
  id: number
  text: string
  tone: 'good' | 'bad' | 'info'
}

const APPROVER_KEY = 'cc-desk-approver'

function readApprover(): string {
  try {
    return localStorage.getItem(APPROVER_KEY) || 'Amine'
  } catch {
    return 'Amine'
  }
}

export default function App() {
  const [health, setHealth] = useState<Health | null>(null)
  const [offline, setOffline] = useState(false)
  const [tickets, setTickets] = useState<Ticket[]>([])
  const [cash, setCash] = useState<Cash | null>(null)
  const [approvals, setApprovals] = useState<Approval[]>([])
  const [drafts, setDrafts] = useState<Draft[]>([])
  const [selected, setSelected] = useState<number | null>(null)
  const [events, setEvents] = useState<AuditEvent[]>([]) // every audit event for the selected ticket
  const [activeRun, setActiveRun] = useState<Run | null>(null)
  const [toasts, setToasts] = useState<Toast[]>([])
  const [approver, setApprover] = useState(readApprover)
  const lastIndex = useRef(-1)

  const toast = useCallback((text: string, tone: Toast['tone'] = 'info') => {
    const id = Date.now() + Math.random()
    setToasts(t => [...t, { id, text, tone }])
    setTimeout(() => setToasts(t => t.filter(x => x.id !== id)), 6000)
  }, [])

  const loadBoard = useCallback(async () => {
    try {
      const [h, t, c, a, d] = await Promise.all([api.health(), api.tickets(), api.cash(), api.approvals(), api.drafts()])
      setHealth(h)
      setTickets(t)
      setCash(c)
      setApprovals(a)
      setDrafts(d)
      setOffline(false)
      const fromHash = Number(window.location.hash.replace('#', ''))
      setSelected(s => s ?? (t.some(x => x.id === fromHash) ? fromHash : t[0]?.id ?? null))
    } catch {
      setOffline(true)
    }
  }, [])

  // First load, pick up a run already in progress (e.g. after a page refresh), and a slow refresh.
  useEffect(() => {
    loadBoard()
    api.runs()
      .then(runs => {
        const live = runs.find(r => r.status === 'queued' || r.status === 'running')
        if (live) {
          setActiveRun(live)
          setSelected(live.ticket_id)
        }
      })
      .catch(() => {})
    const id = setInterval(loadBoard, 8000)
    return () => clearInterval(id)
  }, [loadBoard])

  // #101 in the URL selects ticket 101 (links, screenshots); selecting a ticket updates the URL.
  useEffect(() => {
    const onHash = () => {
      const id = Number(window.location.hash.replace('#', ''))
      if (id) setSelected(id)
    }
    window.addEventListener('hashchange', onHash)
    return () => window.removeEventListener('hashchange', onHash)
  }, [])
  useEffect(() => {
    if (selected !== null && window.location.hash !== `#${selected}`) history.replaceState(null, '', `#${selected}`)
  }, [selected])

  // Full event history whenever the selected ticket changes.
  useEffect(() => {
    if (selected === null) return
    let cancelled = false
    api.events({ ticketId: selected }).then(res => {
      if (cancelled) return
      setEvents(res.events)
      lastIndex.current = res.events.length ? res.events[res.events.length - 1].index : res.total - 1
    }).catch(() => {})
    return () => {
      cancelled = true
    }
  }, [selected])

  // While a run is going: pull new events every second and watch the run status.
  useEffect(() => {
    if (!activeRun || activeRun.status === 'done' || activeRun.status === 'error') return
    const id = setInterval(async () => {
      try {
        const [fresh, run] = await Promise.all([
          api.events({ after: lastIndex.current, ticketId: activeRun.ticket_id }),
          api.run(activeRun.run_id),
        ])
        if (fresh.events.length) {
          lastIndex.current = fresh.events[fresh.events.length - 1].index
          if (selected === activeRun.ticket_id)
            setEvents(ev => {
              const seen = new Set(ev.map(e => e.index))
              return [...ev, ...fresh.events.filter(e => !seen.has(e.index))]
            })
        }
        if (run.status !== activeRun.status) setActiveRun(run)
        if (run.status === 'done') {
          toast(
            run.resolved
              ? `Ticket #${run.ticket_id} resolved: the team finished and nothing is waiting on you.`
              : `Ticket #${run.ticket_id}: agents finished. ${STATUS_LABEL[run.result?.outcome.status ?? ''] ?? ''}`,
            run.resolved ? 'good' : 'info',
          )
          loadBoard()
        } else if (run.status === 'error') {
          toast(`Run failed: ${run.error}`, 'bad')
          loadBoard()
        } else {
          // cash / approvals change mid-run when agents file requests
          api.approvals().then(setApprovals).catch(() => {})
          api.cash().then(setCash).catch(() => {})
        }
      } catch {
        setOffline(true)
      }
    }, 1000)
    return () => clearInterval(id)
  }, [activeRun, selected, loadBoard, toast])

  const ticket = tickets.find(t => t.id === selected) ?? null
  const running = Boolean(activeRun && (activeRun.status === 'queued' || activeRun.status === 'running'))
  const runningHere = running && activeRun?.ticket_id === selected

  // Show the run being watched, or else the latest run recorded for this ticket.
  const shownRunId = useMemo(() => {
    if (activeRun && activeRun.ticket_id === selected) return activeRun.run_id
    return events.length ? events[events.length - 1].run_id : null
  }, [activeRun, selected, events])
  const runEvents = useMemo(() => events.filter(e => e.run_id === shownRunId), [events, shownRunId])
  const runCount = useMemo(() => new Set(events.map(e => e.run_id)).size, [events])

  const startRun = async () => {
    if (!ticket) return
    try {
      const run = await api.runTicket(ticket.id)
      setActiveRun(run)
      toast(`Boss picked up ticket #${ticket.id}.`)
    } catch (err) {
      toast(String((err as Error).message), 'bad')
    }
  }

  const approve = async (id: number) => {
    try {
      const res = await api.approve(id, approver)
      toast(`Paid ${money(res.payment.amount)}. Checking is now ${money(res.payment.balance_after)}.`, 'good')
      if (res.ticket_resolved) toast('Nothing else waiting, so the ticket is resolved.', 'good')
    } catch (err) {
      toast(String((err as Error).message), 'bad')
    }
    await loadBoard()
  }

  const reject = async (id: number) => {
    try {
      const res = (await api.reject(id, approver)) as { ticket_resolved?: boolean }
      toast(`Request #${id} rejected. No money moved.`)
      if (res.ticket_resolved) toast('Nothing else waiting, so the ticket is resolved.', 'good')
    } catch (err) {
      toast(String((err as Error).message), 'bad')
    }
    await loadBoard()
  }

  const resetDb = async () => {
    if (!confirm('Reset the shop database to its original values? Approvals, payments and drafts are cleared. The audit trail is kept.')) return
    try {
      await api.reset()
      setActiveRun(null)
      toast('Shop reset to the original database.', 'info')
      await loadBoard()
    } catch (err) {
      toast(String((err as Error).message), 'bad')
    }
  }

  const changeApprover = (name: string) => {
    setApprover(name)
    try {
      localStorage.setItem(APPROVER_KEY, name)
    } catch {
      /* private window: keep it for this session only */
    }
  }

  const ticketApprovals = approvals.filter(a => a.ticket_id === selected)
  const ticketDrafts = drafts.filter(d => d.ticket_id === selected)
  const pendingCount = approvals.filter(a => a.status === 'pending' || a.status === 'approved').length

  return (
    <div className="app">
      <header className="topbar">
        <div className="brand">
          <span className="brand__mark">CC</span>
          <div>
            <h1>Campus Customs Desk</h1>
            <p>Chapel Street · agents run the shop, you sign the cheques</p>
          </div>
        </div>
        <div className="topbar__meta">
          <span className="chip-lg">Shop date <b>{health?.shop_date ?? '—'}</b></span>
          <span className="chip-lg">Model <b>{health?.model ?? '—'}</b></span>
          <label className="chip-lg approver">
            Approver
            <input value={approver} onChange={e => changeApprover(e.target.value || 'human')} aria-label="Approver name" />
          </label>
          <button className="btn btn--ghost" onClick={resetDb} disabled={running}>Reset shop</button>
        </div>
        <CashMeter cash={cash} />
      </header>

      {offline && (
        <div className="offline">
          Can't reach the backend at <code>{API_URL}</code>. Start it from <code>backend/</code> with{' '}
          <code>uvicorn main:app --reload --port 8000</code>.
        </div>
      )}

      <main className="grid">
        <aside className="col col--tickets">
          <TicketList tickets={tickets} selected={selected} activeRun={running ? activeRun : null} onSelect={setSelected} />
        </aside>

        <section className="col col--work">
          {ticket ? (
            <>
              <div className="ticket-head">
                <div>
                  <div className="eyebrow">Ticket #{ticket.id} · {ticket.type.replace('_', ' ')} · {ticket.requester}</div>
                  <h2>{ticket.subject}</h2>
                  <p className="muted">{ticket.notes?.split('\n')[0]}</p>
                </div>
                <div className="ticket-head__actions">
                  <span className={`pill pill--${runningHere ? 'running' : ticket.status}`}>
                    {runningHere ? <><span className="dot" /> Agents working</> : STATUS_LABEL[ticket.status]}
                  </span>
                  <button className="btn btn--primary btn--lg" onClick={startRun} disabled={running}>
                    {runningHere ? 'Team at work…' : running ? 'Another ticket is running' : runCount ? 'Run the team again' : 'Run the agent team'}
                  </button>
                </div>
              </div>

              <AgentFloor events={runEvents} running={runningHere} />

              <div className="panel">
                <div className="panel__title">
                  <h3>Live log</h3>
                  {shownRunId && (
                    <span className="muted small">
                      run {shownRunId}{runCount > 1 ? ` · latest of ${runCount}` : ''}
                    </span>
                  )}
                </div>
                <Timeline events={runEvents} running={runningHere} />
              </div>
            </>
          ) : (
            <p className="empty">Pick a ticket.</p>
          )}
        </section>

        <aside className="col col--side">
          <div className="panel">
            <div className="panel__title">
              <h3>Needs your approval</h3>
              {pendingCount > 0 && <span className="badge">{pendingCount}</span>}
            </div>
            <Approvals approvals={approvals} cash={cash} approver={approver} onApprove={approve} onReject={reject} />
          </div>

          {runEvents.length > 0 && (
            <div className="panel">
              <div className="panel__title"><h3>Who did what</h3></div>
              <RunSummary events={runEvents} />
            </div>
          )}

          {ticketDrafts.length > 0 && (
            <div className="panel">
              <div className="panel__title"><h3>Drafts on the board</h3></div>
              <Drafts drafts={ticketDrafts} />
            </div>
          )}

          {ticketApprovals.length === 0 && runEvents.length === 0 && (
            <p className="empty small">Run the team on this ticket to see who works it, what they decide and what they need from you.</p>
          )}
        </aside>
      </main>

      <div className="toasts" aria-live="polite">
        {toasts.map(t => <div key={t.id} className={`toast toast--${t.tone}`}>{t.text}</div>)}
      </div>
    </div>
  )
}
