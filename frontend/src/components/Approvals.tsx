import { useState } from 'react'
import { agentMeta, money } from '../agents'
import type { Approval, Cash } from '../types'

const KIND: Record<Approval['kind'], string> = {
  invoice_payment: 'Invoice payment',
  rent_payment: 'Rent payment',
  purchase_order: 'Purchase order',
}

function what(a: Approval): string {
  if (a.kind === 'invoice_payment') return `Invoice #${a.ref_id}`
  if (a.kind === 'rent_payment') return `Lease #${a.ref_id}`
  return `${a.qty} × ${a.sku} ${a.size} · vendor #${a.vendor_id}`
}

interface Props {
  approvals: Approval[]
  cash: Cash | null
  approver: string
  onApprove: (id: number) => Promise<void>
  onReject: (id: number) => Promise<void>
}

/** The human's inbox: every request the agents prepared. Approve & pay is the only way cash goes out. */
export function Approvals({ approvals, cash, approver, onApprove, onReject }: Props) {
  const [busy, setBusy] = useState<number | null>(null)
  const pending = approvals.filter(a => a.status === 'pending' || a.status === 'approved')
  const done = approvals.filter(a => a.status === 'paid' || a.status === 'rejected')

  const act = async (id: number, fn: (id: number) => Promise<void>) => {
    setBusy(id)
    try {
      await fn(id)
    } finally {
      setBusy(null)
    }
  }

  return (
    <div className="approvals">
      {pending.length === 0 && <p className="empty">No requests waiting. Agents will put payments and purchase orders here.</p>}
      {pending.map(a => {
        const short = cash !== null && a.amount > cash.balance
        return (
          <article key={a.id} className={`approval ${short ? 'is-short' : ''}`}>
            <header>
              <span className="eyebrow">{KIND[a.kind]} · #{a.id}</span>
              {a.ticket_id && <span className="muted small">ticket #{a.ticket_id}</span>}
            </header>
            <div className="approval__amount">{money(a.amount)}</div>
            <div className="approval__what">{what(a)}</div>
            <p className="approval__reason">{a.reason}</p>
            <div className="muted small">
              Prepared by {agentMeta(a.requested_by).label}
              {cash && (
                <> · checking after: <b className={short ? 'neg' : ''}>{money(cash.balance - a.amount)}</b></>
              )}
            </div>
            {short && <div className="warn">Not enough cash. The pay tool will refuse this.</div>}
            <div className="approval__actions">
              <button className="btn btn--primary" disabled={busy !== null} onClick={() => act(a.id, onApprove)}>
                {busy === a.id ? 'Paying…' : `Approve & pay as ${approver}`}
              </button>
              {(a.status === 'pending' || a.status === 'approved') && (
                <button className="btn btn--ghost" disabled={busy !== null} onClick={() => act(a.id, onReject)}>
                  Reject
                </button>
              )}
            </div>
          </article>
        )
      })}
      {done.length > 0 && (
        <ul className="ledger">
          {done.map(a => (
            <li key={a.id}>
              <span>{KIND[a.kind]} · {what(a)}</span>
              <span className={a.status === 'paid' ? 'paid' : 'muted'}>
                {a.status === 'paid' ? `−${money(a.amount)}` : 'rejected'}
              </span>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
