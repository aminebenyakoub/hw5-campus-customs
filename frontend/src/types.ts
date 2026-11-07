export type AgentName = 'boss' | 'inventory' | 'accounting' | 'facilities' | 'customer_service'

export type TicketStatus = 'open' | 'in_progress' | 'waiting_approval' | 'blocked' | 'resolved'

export interface Ticket {
  id: number
  type: string
  requester: string
  subject: string
  status: TicketStatus
  state: 'open' | 'resolved'
  notes: string | null
  created_at: string
}

export interface TicketOutcome {
  ticket_id: number
  owner: AgentName
  status: TicketStatus
  decision: string
  approval_ids: number[]
  draft_ids: number[]
  next_steps: string[]
}

export interface Run {
  run_id: string
  ticket_id: number
  status: 'queued' | 'running' | 'done' | 'error'
  model: string
  started_at?: string
  finished_at?: string
  resolved?: boolean
  error?: string
  result?: {
    outcome: TicketOutcome
    delegations: { from: AgentName; to: AgentName; task: string }[]
    usage: { model: string; input_tokens: number; output_tokens: number }
  }
}

export type AuditEventKind =
  | 'agent_start'
  | 'model_response'
  | 'tool_call'
  | 'tool_result'
  | 'delegation'
  | 'agent_end'
  | 'agent_error'

export interface AuditEvent {
  index: number
  ts: string
  run_id: string
  ticket_id: number | null
  agent: AgentName
  depth: number
  chain: AgentName[]
  step: number
  event: AuditEventKind
  model: string | null
  detail: Record<string, unknown>
  input_tokens: number
  output_tokens: number
}

export interface Approval {
  id: number
  kind: 'invoice_payment' | 'rent_payment' | 'purchase_order'
  ticket_id: number | null
  ref_id: number | null
  vendor_id: number | null
  sku: string | null
  size: string | null
  qty: number | null
  amount: number
  account: string
  reason: string
  requested_by: string
  status: 'pending' | 'approved' | 'rejected' | 'paid'
  decided_by: string | null
  decided_at: string | null
  created_at: string
}

export interface Cash {
  name: string
  balance: number
  date: string
  requested_not_paid: number
  balance_after_requests: number
}

export interface Draft {
  id: number
  ticket_id: number | null
  recipient: string
  subject: string
  body: string
  written_by: string
  status: string
  created_at: string
}

export interface Health {
  ok: boolean
  model: string
  database: string
  shop_date: string
}
