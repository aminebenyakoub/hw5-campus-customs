"""Data types shared by the agent team, the audit trail and (later) the API."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from pydantic import BaseModel, Field

AgentName = Literal["boss", "inventory", "accounting", "facilities", "customer_service"]
AGENT_NAMES: tuple[AgentName, ...] = (
    "boss",
    "inventory",
    "accounting",
    "facilities",
    "customer_service",
)
TicketStatus = Literal["open", "in_progress", "waiting_approval", "blocked", "resolved"]


class TicketOutcome(BaseModel):
    """Boss's final call on one ticket (structured output of the Boss loop)."""

    ticket_id: int
    owner: AgentName = Field(description="Agent that owns the follow-up on this ticket.")
    status: TicketStatus = Field(description="Status the Boss set on the ticket with update_ticket.")
    decision: str = Field(description="Final call in 1-3 sentences, using only facts from tools.")
    approval_ids: list[int] = Field(default_factory=list, description="Approval requests waiting on a human.")
    draft_ids: list[int] = Field(default_factory=list, description="Customer message drafts left on the board.")
    next_steps: list[str] = Field(default_factory=list, description="What must happen next, and who does it.")


class AuditEvent(BaseModel):
    """One line of output/audit_trail.json: one step of one agent loop."""

    ts: str
    run_id: str
    ticket_id: int | None
    agent: AgentName
    depth: int = Field(description="0 = Boss, 1 = delegated by Boss, 2 = delegated by a specialist.")
    chain: list[AgentName] = Field(description="Who delegated to whom to reach this agent.")
    step: int = Field(description="Model-call number inside this agent's loop.")
    event: Literal[
        "agent_start",
        "model_response",
        "tool_call",
        "tool_result",
        "delegation",
        "agent_end",
        "agent_error",
    ]
    model: str | None = None
    detail: dict[str, Any] = Field(default_factory=dict)
    input_tokens: int = 0
    output_tokens: int = 0


@dataclass
class TicketRun:
    """Budget and bookkeeping shared by every agent working on one ticket."""

    run_id: str
    ticket_id: int | None
    delegations: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    delegation_log: list[dict] = field(default_factory=list)

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens


@dataclass
class AgentDeps:
    """What each agent loop gets as Pydantic AI deps."""

    run: TicketRun
    agent: AgentName
    chain: list[AgentName]

    @property
    def depth(self) -> int:
        return len(self.chain) - 1
