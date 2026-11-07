"""The Campus Customs agent team: Boss, Inventory, Accounting, Facilities, Customer Service.

Full connectivity: every agent has a `delegate` tool that can hand a task to any other agent, so a
specialist can ask another specialist for help (e.g. Facilities -> Accounting to prepare a rent payment).
Loops are bounded by depth, a per-ticket delegation budget, a per-ticket token budget and Pydantic AI
usage limits. Every loop step is appended to output/audit_trail.json.
"""

from __future__ import annotations

import json
import uuid

from pydantic_ai import Agent, RunContext, UsageLimits
from pydantic_ai.messages import TextPart, ToolCallPart, ToolReturnPart, RetryPromptPart

import audit
from config import (
    AGENT_REQUEST_LIMIT,
    AGENT_TOOL_CALLS_LIMIT,
    BOSS_REQUEST_LIMIT,
    MAX_DELEGATION_DEPTH,
    MAX_DELEGATIONS_PER_TICKET,
    MAX_TOKENS_PER_TICKET,
    MODEL_NAME,
    build_model,
    load_prompt,
)
from mcp_tools import build_toolset, tools_for
from models import AGENT_NAMES, AgentDeps, AgentName, TicketOutcome, TicketRun

SHOP_RULES = load_prompt("shop_rules")

# One MCP connection (one server process) shared by every agent in a run.
TOOLSET = build_toolset()


async def delegate(ctx: RunContext[AgentDeps], to_agent: AgentName, task: str) -> str:
    """Hand a task to another agent on the team and get its answer back.

    Args:
        to_agent: One of boss, inventory, accounting, facilities, customer_service (not yourself).
        task: A self-contained request: ticket id, the facts you already have, and exactly what you need back.
    """
    deps = ctx.deps
    run = deps.run
    refusal = None
    if to_agent == deps.agent:
        refusal = "You cannot delegate to yourself."
    elif to_agent in deps.chain:
        refusal = f"{to_agent} is already waiting on you in this chain ({' -> '.join(deps.chain)}). Answer it yourself."
    elif deps.depth >= MAX_DELEGATION_DEPTH:
        refusal = "Delegation depth limit reached. Use your own tools and answer with what you have."
    elif run.delegations >= MAX_DELEGATIONS_PER_TICKET:
        refusal = "Delegation budget for this ticket is used up. Answer with what you have."
    elif run.total_tokens >= MAX_TOKENS_PER_TICKET:
        refusal = "Token budget for this ticket is used up. Answer with what you have."
    audit.append(
        deps, "delegation", ctx.run_step,
        {"to": to_agent, "task": task, "accepted": refusal is None, "refusal": refusal},
    )
    if refusal:
        return refusal

    run.delegations += 1
    run.delegation_log.append({"from": deps.agent, "to": to_agent, "task": task})
    sub = AgentDeps(run=run, agent=to_agent, chain=[*deps.chain, to_agent])
    reply = await run_agent(sub, task)
    return f"[{to_agent}] {reply}"


def _build_agent(name: AgentName) -> Agent:
    return Agent(
        name=name,
        deps_type=AgentDeps,
        output_type=TicketOutcome if name == "boss" else str,
        instructions=f"{load_prompt(name)}\n\n{SHOP_RULES}",
        toolsets=[tools_for(TOOLSET, name)],
        tools=[delegate],
        defer_model_check=True,
    )


AGENTS: dict[AgentName, Agent] = {name: _build_agent(name) for name in AGENT_NAMES}


def _log_request_parts(deps: AgentDeps, step: int, parts) -> None:
    for part in parts:
        if isinstance(part, ToolReturnPart) and part.tool_name != "delegate":
            audit.append(deps, "tool_result", step, {"tool": part.tool_name, "result": part.model_response_str()})
        elif isinstance(part, RetryPromptPart):
            audit.append(deps, "tool_result", step, {"tool": part.tool_name, "retry": part.model_response()})


def _log_response(deps: AgentDeps, step: int, response) -> None:
    usage = response.usage
    deps.run.input_tokens += usage.input_tokens
    deps.run.output_tokens += usage.output_tokens
    texts = [p.content for p in response.parts if isinstance(p, TextPart) and p.content.strip()]
    calls = [p for p in response.parts if isinstance(p, ToolCallPart)]
    audit.append(
        deps, "model_response", step,
        {"text": "\n".join(texts), "tool_calls": [c.tool_name for c in calls]},
        model=response.model_name or MODEL_NAME,
        input_tokens=usage.input_tokens, output_tokens=usage.output_tokens,
    )
    for c in calls:
        if c.tool_name != "delegate":  # delegations get their own audit line
            audit.append(deps, "tool_call", step, {"tool": c.tool_name, "args": c.args_as_dict()})


async def run_agent(deps: AgentDeps, task: str):
    """Run one agent loop (model call -> tool calls -> model call ...) and audit every step."""
    agent = AGENTS[deps.agent]
    is_boss = deps.agent == "boss"
    limits = UsageLimits(
        request_limit=BOSS_REQUEST_LIMIT if is_boss else AGENT_REQUEST_LIMIT,
        tool_calls_limit=AGENT_TOOL_CALLS_LIMIT,
    )
    audit.append(deps, "agent_start", 0, {"task": task}, model=MODEL_NAME)
    step = 0
    try:
        async with agent.iter(task, deps=deps, model=build_model(), usage_limits=limits) as agent_run:
            async for node in agent_run:
                if Agent.is_model_request_node(node):
                    _log_request_parts(deps, step, node.request.parts)
                elif Agent.is_call_tools_node(node):
                    step += 1
                    _log_response(deps, step, node.model_response)
        output = agent_run.result.output
    except Exception as exc:  # report to the caller instead of crashing the whole ticket
        audit.append(deps, "agent_error", step, {"error": f"{type(exc).__name__}: {exc}"})
        if is_boss:
            raise
        return f"{deps.agent} could not finish: {type(exc).__name__}: {exc}"

    shown = output.model_dump() if isinstance(output, TicketOutcome) else output
    audit.append(deps, "agent_end", step, {"output": shown})
    return output


def new_run_id() -> str:
    return uuid.uuid4().hex[:8]


async def run_ticket(ticket_id: int, run_id: str | None = None) -> dict:
    """Boss works one ticket end to end, delegating as needed. Returns the outcome and usage."""
    run = TicketRun(run_id=run_id or new_run_id(), ticket_id=ticket_id)
    deps = AgentDeps(run=run, agent="boss", chain=["boss"])
    task = (
        f"Work ticket {ticket_id}. Read it with get_ticket, delegate to the right teammates, "
        f"set its status with update_ticket, then give your final call."
    )
    async with TOOLSET:
        outcome: TicketOutcome = await run_agent(deps, task)
    return {
        "run_id": run.run_id,
        "ticket_id": ticket_id,
        "outcome": outcome.model_dump(),
        "delegations": run.delegation_log,
        "usage": {"model": MODEL_NAME, "input_tokens": run.input_tokens, "output_tokens": run.output_tokens},
    }


def pretty(result: dict) -> str:
    return json.dumps(result, indent=2)
