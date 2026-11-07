import type { AgentName, AuditEvent } from './types'

export interface AgentMeta {
  name: AgentName
  label: string
  role: string
  glyph: string
}

export const AGENTS: AgentMeta[] = [
  { name: 'boss', label: 'Boss', role: 'Routes tickets · final call', glyph: '★' },
  { name: 'inventory', label: 'Inventory', role: 'Stock · vendors · restock', glyph: '▦' },
  { name: 'accounting', label: 'Accounting', role: 'Cash · invoices · margins', glyph: '$' },
  { name: 'facilities', label: 'Facilities', role: 'Lease · rent · space', glyph: '⌂' },
  { name: 'customer_service', label: 'Customer Service', role: 'Drafts replies', glyph: '✉' },
]

export const agentMeta = (name: string): AgentMeta =>
  AGENTS.find(a => a.name === name) ?? { name: name as AgentName, label: name, role: '', glyph: '•' }

export const money = (n: number) =>
  n.toLocaleString('en-US', { style: 'currency', currency: 'USD', minimumFractionDigits: 2 })

export function formatArgs(args: unknown): string {
  if (!args || typeof args !== 'object') return ''
  return Object.entries(args as Record<string, unknown>)
    .filter(([k]) => !['reason', 'body', 'note', 'requested_by', 'written_by'].includes(k))
    .map(([k, v]) => `${k}=${typeof v === 'string' ? v : JSON.stringify(v)}`)
    .join(', ')
}

/** Agents sometimes answer in markdown; the desk shows plain text. */
export const plain = (s: string) => s.replace(/\*\*|__|`/g, '').replace(/^#+\s*/gm, '')

export function outputText(output: unknown): string {
  if (typeof output === 'string') return plain(output)
  if (output && typeof output === 'object' && 'decision' in output) return plain(String((output as { decision: string }).decision))
  return ''
}

/** Plain-language "what is this agent doing" from its latest audit event. */
export function activityOf(e: AuditEvent | undefined): string {
  if (!e) return 'Idle'
  const d = e.detail
  switch (e.event) {
    case 'agent_start':
      return 'Reading the task…'
    case 'model_response': {
      const calls = (d.tool_calls as string[]) ?? []
      if (calls.includes('final_result')) return 'Writing the final call…'
      return calls.length ? `Deciding: ${calls.join(', ')}` : 'Thinking…'
    }
    case 'tool_call':
      return `Using ${d.tool}`
    case 'tool_result':
      return `Reading ${d.tool} result`
    case 'delegation':
      return d.accepted ? `Asked ${agentMeta(String(d.to)).label}` : `Delegation refused`
    case 'agent_end':
      return 'Done'
    case 'agent_error':
      return 'Hit an error'
  }
}
