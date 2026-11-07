import type { Approval, AuditEvent, Cash, Draft, Health, Run, Ticket } from './types'

// The FastAPI backend from Problem 7.
export const API_URL = (import.meta.env.VITE_API_URL as string | undefined) ?? 'http://localhost:8000'

async function call<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...init,
  })
  const body = await res.json().catch(() => ({}))
  if (!res.ok) throw new Error((body as { detail?: string }).detail ?? `${res.status} ${res.statusText}`)
  return body as T
}

export const api = {
  health: () => call<Health>('/api/health'),
  tickets: () => call<Ticket[]>('/api/tickets'),
  runTicket: (id: number) => call<Run>(`/api/tickets/${id}/run`, { method: 'POST' }),
  resolveTicket: (id: number, by: string) =>
    call(`/api/tickets/${id}/resolve`, { method: 'POST', body: JSON.stringify({ approved_by: by }) }),
  runs: () => call<Run[]>('/api/runs'),
  run: (runId: string) => call<Run>(`/api/runs/${runId}`),
  events: (params: { after?: number; ticketId?: number; limit?: number }) => {
    const q = new URLSearchParams()
    if (params.after !== undefined) q.set('after', String(params.after))
    if (params.ticketId !== undefined) q.set('ticket_id', String(params.ticketId))
    q.set('limit', String(params.limit ?? 1000))
    return call<{ total: number; events: AuditEvent[] }>(`/api/events?${q}`)
  },
  approvals: () => call<Approval[]>('/api/approvals'),
  approve: (id: number, by: string) =>
    call<{ payment: { amount: number; balance_after: number }; ticket_resolved: boolean }>(
      `/api/approvals/${id}/approve`,
      { method: 'POST', body: JSON.stringify({ approved_by: by }) },
    ),
  reject: (id: number, by: string) =>
    call(`/api/approvals/${id}/reject`, { method: 'POST', body: JSON.stringify({ approved_by: by }) }),
  cash: () => call<Cash>('/api/cash'),
  drafts: () => call<Draft[]>('/api/drafts'),
  reset: () => call<{ ok: boolean }>('/api/reset', { method: 'POST' }),
}
