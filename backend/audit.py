"""Append-only audit trail in output/audit_trail.json (a JSON array; never wiped between runs)."""

from __future__ import annotations

import json
import threading
from datetime import datetime
from typing import Any

from config import AUDIT_TEXT_LIMIT, AUDIT_TRAIL
from models import AgentDeps, AuditEvent

_lock = threading.Lock()


def clip(value: Any, limit: int = AUDIT_TEXT_LIMIT) -> Any:
    """Keep the audit readable and small: long strings are cut, nested values are clipped."""
    if isinstance(value, str):
        return value if len(value) <= limit else value[:limit] + f"... [+{len(value) - limit} chars]"
    if isinstance(value, dict):
        return {k: clip(v, limit) for k, v in value.items()}
    if isinstance(value, list):
        return [clip(v, limit) for v in value]
    return value


def read_trail() -> list[dict]:
    if not AUDIT_TRAIL.exists():
        return []
    text = AUDIT_TRAIL.read_text(encoding="utf-8").strip()
    return json.loads(text) if text else []


def append(deps: AgentDeps, event: str, step: int, detail: dict | None = None, *,
           model: str | None = None, input_tokens: int = 0, output_tokens: int = 0) -> None:
    record = AuditEvent(
        ts=datetime.now().isoformat(timespec="seconds"),
        run_id=deps.run.run_id,
        ticket_id=deps.run.ticket_id,
        agent=deps.agent,
        depth=deps.depth,
        chain=list(deps.chain),
        step=step,
        event=event,
        model=model,
        detail=clip(detail or {}),
        input_tokens=input_tokens,
        output_tokens=output_tokens,
    )
    with _lock:
        trail = read_trail()
        trail.append(record.model_dump())
        AUDIT_TRAIL.parent.mkdir(parents=True, exist_ok=True)
        tmp = AUDIT_TRAIL.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(trail, indent=2), encoding="utf-8")
        tmp.replace(AUDIT_TRAIL)
