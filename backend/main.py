"""Campus Customs API for the React dashboard.

Start from the backend/ folder:
    uvicorn main:app --reload --port 8000

Shop data is read and written through the campus-customs MCP server (same tools the agents use); the only
direct file operation is the reset, which copies the original database over the working copy.
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

import audit
from agents import new_run_id, run_ticket
from config import MODEL_NAME, WORKING_DB
from mcp_tools import mcp_client
from reset_db import reset_working_db

app = FastAPI(title="Campus Customs API", version="1.0")
app.add_middleware(
    CORSMiddleware,
    # The Vite dashboard (npm run dev) plus any other local port
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_origin_regex=r"http://(localhost|127\.0\.0\.1)(:\d+)?",
    allow_methods=["*"],
    allow_headers=["*"],
)

# One agent run at a time: every run writes to the same working database.
_run_lock = asyncio.Lock()
RUNS: dict[str, dict[str, Any]] = {}
_tasks: set[asyncio.Task] = set()  # keep background runs referenced until they finish


async def mcp(tool: str, **args) -> Any:
    """Call one campus-customs MCP tool and return its structured result."""
    async with mcp_client() as client:
        result = await client.call_tool(tool, args)
    data = result.structured_content or {}
    # FastMCP wraps list results as {"result": [...]}
    return data.get("result", data) if set(data) == {"result"} else data


async def settle_ticket(ticket_id: int | None, why: str) -> bool:
    """Mark a ticket resolved once the team is done and nothing is waiting on a human.

    Stays open while any of its payment / purchase requests is pending or approved-but-unpaid, or when the
    Boss marked it blocked.
    """
    if ticket_id is None:
        return False
    ticket = await mcp("get_ticket", ticket_id=ticket_id)
    if not ticket.get("found") or ticket["status"] in ("resolved", "blocked"):
        return False
    waiting = [
        a for a in await mcp("list_approvals", status="all")
        if a["ticket_id"] == ticket_id and a["status"] in ("pending", "approved")
    ]
    if waiting:
        return False
    await mcp("update_ticket", ticket_id=ticket_id, status="resolved", note=why)
    return True


class Decision(BaseModel):
    approved_by: str = "human"
    note: str = ""


# ---------------------------------------------------------------- tickets


@app.get("/api/tickets")
async def list_tickets():
    """Every ticket with its status and whether it is resolved."""
    tickets = await mcp("list_tickets")
    return [
        {
            "id": t["id"],
            "type": t["type"],
            "requester": t["requester"],
            "subject": t["subject"],
            "status": t["status"],
            "state": "resolved" if t["is_resolved"] else "open",
            "notes": t["notes"],
            "created_at": t["created_at"],
        }
        for t in tickets
    ]


async def _run_in_background(run_id: str, ticket_id: int) -> None:
    async with _run_lock:
        RUNS[run_id]["status"] = "running"
        RUNS[run_id]["started_at"] = datetime.now().isoformat(timespec="seconds")
        try:
            RUNS[run_id]["result"] = await run_ticket(ticket_id, run_id=run_id)
            RUNS[run_id]["status"] = "done"
            RUNS[run_id]["resolved"] = await settle_ticket(
                ticket_id, "Agent run finished; nothing waiting on a human."
            )
        except Exception as exc:
            RUNS[run_id]["status"] = "error"
            RUNS[run_id]["error"] = f"{type(exc).__name__}: {exc}"
        RUNS[run_id]["finished_at"] = datetime.now().isoformat(timespec="seconds")


@app.post("/api/tickets/{ticket_id}/run", status_code=202)
async def run_ticket_route(ticket_id: int):
    """Start the agent team on one ticket. Returns a run_id at once; poll /api/runs/{run_id} and /api/events."""
    ticket = await mcp("get_ticket", ticket_id=ticket_id)
    if not ticket.get("found"):
        raise HTTPException(404, f"No ticket {ticket_id}.")
    if any(r["ticket_id"] == ticket_id and r["status"] in ("queued", "running") for r in RUNS.values()):
        raise HTTPException(409, f"Ticket {ticket_id} already has a run in progress.")
    run_id = new_run_id()
    RUNS[run_id] = {"run_id": run_id, "ticket_id": ticket_id, "status": "queued", "model": MODEL_NAME}
    task = asyncio.create_task(_run_in_background(run_id, ticket_id))
    _tasks.add(task)
    task.add_done_callback(_tasks.discard)
    return RUNS[run_id]


@app.post("/api/tickets/{ticket_id}/resolve")
async def resolve_ticket(ticket_id: int, decision: Decision | None = None):
    """A human marks a ticket resolved by hand (e.g. a blocked ticket handled outside the desk)."""
    decision = decision or Decision()
    result = await mcp(
        "update_ticket", ticket_id=ticket_id, status="resolved",
        note=f"Resolved by {decision.approved_by}. {decision.note}".strip(),
    )
    if not result.get("ok"):
        raise HTTPException(404, result.get("error", "Could not resolve."))
    return result


@app.get("/api/runs")
async def list_runs():
    """Agent runs started since the server started, newest first."""
    return list(reversed(RUNS.values()))


@app.get("/api/runs/{run_id}")
async def get_run(run_id: str):
    """Status of one run (queued / running / done / error) and the Boss's outcome when done."""
    if run_id not in RUNS:
        raise HTTPException(404, f"No run {run_id}.")
    return RUNS[run_id]


# ---------------------------------------------------------------- events


@app.get("/api/events")
async def recent_events(
    limit: int = Query(100, ge=1, le=1000),
    after: int = Query(-1, description="Only events with index > after (for incremental refresh)."),
    ticket_id: int | None = None,
    run_id: str | None = None,
):
    """Recent audit-trail events: which agent said what and which tool it used."""
    trail = audit.read_trail()
    events = [
        {"index": i, **e}
        for i, e in enumerate(trail)
        if i > after
        and (ticket_id is None or e["ticket_id"] == ticket_id)
        and (run_id is None or e["run_id"] == run_id)
    ]
    return {"total": len(trail), "events": events[-limit:]}


# ---------------------------------------------------------------- approvals and money


@app.get("/api/approvals")
async def list_approvals(status: str = "all"):
    """Payment / purchase-order requests prepared by the agents."""
    return await mcp("list_approvals", status=status)


@app.post("/api/approvals/{approval_id}/approve")
async def approve(approval_id: int, decision: Decision | None = None):
    """A human approves a request; this route then pays it (the only place cash goes down)."""
    decision = decision or Decision()
    decided = await mcp(
        "decide_approval", approval_id=approval_id, decision="approved",
        decided_by=decision.approved_by, note=decision.note,
    )
    # An already-approved but unpaid request (e.g. cash was short last time) can be retried.
    if not decided.get("ok") and "already approved" not in decided.get("error", ""):
        raise HTTPException(409, decided.get("error", "Could not approve."))
    paid = await mcp("pay_approved", approval_id=approval_id)
    if not paid.get("ok"):
        raise HTTPException(409, paid.get("error", "Payment refused."))
    ticket_id = next(
        (a["ticket_id"] for a in await mcp("list_approvals", status="all") if a["id"] == approval_id), None
    )
    resolved = await settle_ticket(
        ticket_id, f"Approval {approval_id} paid (${paid['amount']:,.2f}) after human approval by {decision.approved_by}."
    )
    return {
        "approval_id": approval_id,
        "approved_by": decision.approved_by,
        "payment": paid,
        "ticket_id": ticket_id,
        "ticket_resolved": resolved,
    }


@app.post("/api/approvals/{approval_id}/reject")
async def reject(approval_id: int, decision: Decision | None = None):
    """A human rejects a request. No money moves."""
    decision = decision or Decision()
    decided = await mcp(
        "decide_approval", approval_id=approval_id, decision="rejected",
        decided_by=decision.approved_by, note=decision.note,
    )
    if not decided.get("ok"):
        raise HTTPException(409, decided.get("error", "Could not reject."))
    ticket_id = decided["approval"]["ticket_id"]
    resolved = await settle_ticket(
        ticket_id, f"Approval {approval_id} rejected by {decision.approved_by}; nothing paid."
    )
    return {**decided, "ticket_id": ticket_id, "ticket_resolved": resolved}


@app.get("/api/cash")
async def cash():
    """Current checking balance from cash_accounts (plus money requested but not yet paid)."""
    accounts = await mcp("get_cash_balance")
    checking = next((a for a in accounts if a["name"] == "checking"), None)
    if checking is None:
        raise HTTPException(404, "No checking account.")
    return checking


@app.get("/api/drafts")
async def drafts(ticket_id: int | None = None):
    """Customer message drafts the agents left on the board (never sent)."""
    return await mcp("list_drafts", ticket_id=ticket_id)


# ---------------------------------------------------------------- reset


@app.post("/api/reset")
async def reset():
    """Copy the original database over the working copy. The audit trail is kept."""
    if _run_lock.locked():
        raise HTTPException(409, "An agent run is in progress; wait for it to finish.")
    reset_working_db()
    return {"ok": True, "database": WORKING_DB.name, "cash": await cash()}


@app.get("/api/health")
async def health():
    """Model, working database and the shop's date (desk.date_today)."""
    desk = await mcp("get_shop_date")
    return {"ok": True, "model": MODEL_NAME, "database": WORKING_DB.name, "shop_date": desk["date_today"]}
