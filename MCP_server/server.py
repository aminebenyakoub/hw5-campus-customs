"""Campus Customs MCP server.

Exposes the shop database (working copy data/campus_customs_new.db) as tools for the agent team.
Every tool returns only what is in the database; when a record is missing it says so instead of guessing.

Money rules enforced here (not in prompts): agents can only *request* payments and purchase orders; a human
decides them with `decide_approval` (never given to agents); `pay_approved` refuses anything not approved by a
human or that would push a cash account below zero.
"""

import os
import sqlite3
from datetime import date, datetime
from pathlib import Path
from typing import Literal

from fastmcp import FastMCP

DB_PATH = Path(
    os.environ.get(
        "CAMPUS_DB_PATH",
        Path(__file__).resolve().parent.parent / "data" / "campus_customs_new.db",
    )
)

mcp = FastMCP("campus-customs")

# Board tables the agents write to. They live only in the working copy and are created on first use,
# so the original database stays untouched and a reset simply drops them.
_BOARD_SCHEMA = """
CREATE TABLE IF NOT EXISTS approvals (
    id INTEGER PRIMARY KEY,
    kind TEXT NOT NULL,              -- invoice_payment | rent_payment | purchase_order
    ticket_id INTEGER,
    ref_id INTEGER,                  -- invoice id, lease id, or vendor id (purchase order)
    vendor_id INTEGER,
    sku TEXT,
    size TEXT,
    qty INTEGER,
    amount REAL NOT NULL,
    account TEXT NOT NULL,
    reason TEXT NOT NULL,
    requested_by TEXT NOT NULL,
    status TEXT NOT NULL,            -- pending | approved | rejected | paid
    decided_by TEXT,
    decided_at TEXT,
    decision_note TEXT,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS drafts (
    id INTEGER PRIMARY KEY,
    ticket_id INTEGER,
    recipient TEXT NOT NULL,
    subject TEXT NOT NULL,
    body TEXT NOT NULL,
    written_by TEXT NOT NULL,
    status TEXT NOT NULL,            -- draft (never sent: drafts stay on the board)
    created_at TEXT NOT NULL
);
"""


def _connect() -> sqlite3.Connection:
    if not DB_PATH.exists():
        raise FileNotFoundError(f"Working database not found: {DB_PATH}")
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.executescript(_BOARD_SCHEMA)
    return conn


def _today(conn: sqlite3.Connection) -> str:
    return conn.execute("SELECT date_today FROM desk LIMIT 1").fetchone()["date_today"]


def _days_between(start: str, end: str) -> int:
    return (date.fromisoformat(end) - date.fromisoformat(start)).days


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _open_invoices(conn: sqlite3.Connection, vendor_id: int) -> list[dict]:
    today = _today(conn)
    rows = conn.execute(
        "SELECT id, amount, due_date, status, description FROM invoices "
        "WHERE vendor_id = ? AND status != 'paid' ORDER BY due_date",
        (vendor_id,),
    ).fetchall()
    return [
        {**dict(r), "days_overdue": max(0, _days_between(r["due_date"], today))} for r in rows
    ]


# ---------------------------------------------------------------- shop context


@mcp.tool
def get_shop_date() -> dict:
    """Return the shop's 'today' (desk.date_today) and desk notes. Use it to judge what is due or overdue."""
    with _connect() as conn:
        row = conn.execute("SELECT date_today, notes FROM desk LIMIT 1").fetchone()
        return dict(row)


@mcp.tool
def list_open_tickets() -> list[dict]:
    """List every ticket that is not resolved (tickets table), oldest first."""
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM tickets WHERE status != 'resolved' ORDER BY created_at"
        ).fetchall()
        return [dict(r) for r in rows]


@mcp.tool
def list_tickets() -> list[dict]:
    """List every ticket, resolved or not (tickets table), with an `is_resolved` flag."""
    with _connect() as conn:
        rows = conn.execute("SELECT * FROM tickets ORDER BY id").fetchall()
        return [{**dict(r), "is_resolved": r["status"] == "resolved"} for r in rows]


@mcp.tool
def get_ticket(ticket_id: int) -> dict:
    """Return one ticket with all its fields (type, requester, sku/size/qty, lease_id, invoice_id, status, notes)."""
    with _connect() as conn:
        row = conn.execute("SELECT * FROM tickets WHERE id = ?", (ticket_id,)).fetchone()
        if row is None:
            return {"found": False, "ticket_id": ticket_id, "message": "No ticket with this id."}
        return {"found": True, **dict(row)}


# ---------------------------------------------------------------- inventory


@mcp.tool
def check_stock(sku: str, size: str) -> dict:
    """Return on-hand quantity and shelf location for one SKU in one size (inventory table).

    Use it to tell whether a customer order (e.g. ticket 101) can be filled from stock.
    """
    with _connect() as conn:
        row = conn.execute(
            "SELECT sku, name, size, qty, location FROM inventory WHERE sku = ? AND size = ?",
            (sku, size),
        ).fetchone()
        if row is None:
            sizes = [
                r["size"]
                for r in conn.execute("SELECT size FROM inventory WHERE sku = ?", (sku,))
            ]
            return {
                "found": False,
                "sku": sku,
                "size": size,
                "message": "No inventory record for this SKU and size.",
                "sizes_on_record": sizes,
            }
        return {"found": True, **dict(row), "in_stock": row["qty"] > 0}


@mcp.tool
def list_inventory(sku: str | None = None) -> list[dict]:
    """List stock rows (inventory table) for one SKU across all sizes, or every row if no SKU is given."""
    with _connect() as conn:
        if sku:
            rows = conn.execute(
                "SELECT * FROM inventory WHERE sku = ? ORDER BY size", (sku,)
            ).fetchall()
        else:
            rows = conn.execute("SELECT * FROM inventory ORDER BY sku, size").fetchall()
        return [dict(r) for r in rows]


@mcp.tool
def list_vendors() -> list[dict]:
    """List every vendor with specialty, lead time, open (unpaid) invoices and whether it can ship new product.

    Reads vendors + invoices. A vendor will not ship new products while it has an open unpaid invoice;
    `expected_arrival_if_ordered_today` = desk.date_today + lead_days, only meaningful once it can ship.
    """
    with _connect() as conn:
        today = _today(conn)
        out = []
        for v in conn.execute("SELECT * FROM vendors ORDER BY id").fetchall():
            open_inv = _open_invoices(conn, v["id"])
            out.append(
                {
                    **dict(v),
                    "open_invoices": open_inv,
                    "can_ship_new_product": not open_inv,
                    "expected_arrival_if_ordered_today": conn.execute(
                        "SELECT date(?, '+' || ? || ' days') AS d", (today, v["lead_days"])
                    ).fetchone()["d"],
                }
            )
        return out


# ---------------------------------------------------------------- money


@mcp.tool
def get_sku_pricing(sku: str) -> dict:
    """Return unit cost, list price and margin at list price for one SKU (pricing table).

    Use it to judge how much discount a bulk price request (e.g. ticket 103) can take without selling at a loss.
    """
    with _connect() as conn:
        row = conn.execute(
            "SELECT sku, unit_cost, list_price FROM pricing WHERE sku = ?", (sku,)
        ).fetchone()
        if row is None:
            return {"found": False, "sku": sku, "message": "No pricing record for this SKU."}
        cost, price = row["unit_cost"], row["list_price"]
        margin = price - cost
        return {
            "found": True,
            "sku": sku,
            "unit_cost": cost,
            "list_price": price,
            "margin_per_unit": round(margin, 2),
            # Also the largest discount (% off list) before the sale loses money
            "margin_pct_of_price": round(margin / price * 100, 1),
        }


@mcp.tool
def quote_discount(sku: str, qty: int, discount_pct: float) -> dict:
    """Price a discounted order from the pricing table: unit price, revenue, cost and margin at that discount."""
    with _connect() as conn:
        row = conn.execute(
            "SELECT unit_cost, list_price FROM pricing WHERE sku = ?", (sku,)
        ).fetchone()
        if row is None:
            return {"found": False, "sku": sku, "message": "No pricing record for this SKU."}
        if qty <= 0 or not 0 <= discount_pct < 100:
            return {"found": True, "error": "qty must be > 0 and discount_pct between 0 and 100."}
        unit_price = round(row["list_price"] * (1 - discount_pct / 100), 2)
        margin_unit = round(unit_price - row["unit_cost"], 2)
        return {
            "found": True,
            "sku": sku,
            "qty": qty,
            "discount_pct": discount_pct,
            "list_price": row["list_price"],
            "unit_cost": row["unit_cost"],
            "discounted_unit_price": unit_price,
            "margin_per_unit": margin_unit,
            "margin_pct_of_price": round(margin_unit / unit_price * 100, 1) if unit_price else None,
            "order_revenue": round(unit_price * qty, 2),
            "order_cost": round(row["unit_cost"] * qty, 2),
            "order_margin": round(margin_unit * qty, 2),
            "sells_at_loss": margin_unit < 0,
        }


@mcp.tool
def get_cash_balance() -> list[dict]:
    """Return every cash account with its balance (cash_accounts), minus money already approved but not yet paid."""
    with _connect() as conn:
        out = []
        for a in conn.execute("SELECT * FROM cash_accounts ORDER BY name").fetchall():
            committed = conn.execute(
                "SELECT COALESCE(SUM(amount), 0) AS s FROM approvals "
                "WHERE account = ? AND status IN ('pending', 'approved')",
                (a["name"],),
            ).fetchone()["s"]
            out.append(
                {
                    **dict(a),
                    "requested_not_paid": round(committed, 2),
                    "balance_after_requests": round(a["balance"] - committed, 2),
                }
            )
        return out


@mcp.tool
def list_invoices(status: Literal["open", "paid", "all"] = "open") -> list[dict]:
    """List vendor invoices (invoices + vendors) with days overdue versus desk.date_today."""
    with _connect() as conn:
        today = _today(conn)
        sql = (
            "SELECT i.*, v.name AS vendor_name FROM invoices i JOIN vendors v ON v.id = i.vendor_id"
        )
        if status == "open":
            sql += " WHERE i.status != 'paid'"
        elif status == "paid":
            sql += " WHERE i.status = 'paid'"
        rows = conn.execute(sql + " ORDER BY i.due_date").fetchall()
        return [
            {
                **dict(r),
                "days_overdue": max(0, _days_between(r["due_date"], today))
                if r["status"] != "paid"
                else 0,
            }
            for r in rows
        ]


@mcp.tool
def get_lease_rent_due(lease_id: int) -> dict:
    """Return a lease's landlord, monthly rent and next due date, with days until due (leases + desk tables).

    Use it to confirm what a rent notice (e.g. ticket 102) is asking for before anyone prepares a payment.
    """
    with _connect() as conn:
        row = conn.execute(
            "SELECT id, space_name, landlord, monthly_rent, next_due, notes FROM leases WHERE id = ?",
            (lease_id,),
        ).fetchone()
        if row is None:
            return {"found": False, "lease_id": lease_id, "message": "No lease with this id."}
        today = _today(conn)
        days = _days_between(today, row["next_due"])
        return {
            "found": True,
            **dict(row),
            "date_today": today,
            "days_until_due": days,
            "overdue": days < 0,
        }


def _insert_approval(conn: sqlite3.Connection, **fields) -> dict:
    fields.update(status="pending", created_at=_now())
    cols = ", ".join(fields)
    marks = ", ".join("?" for _ in fields)
    cur = conn.execute(f"INSERT INTO approvals ({cols}) VALUES ({marks})", tuple(fields.values()))
    row = conn.execute("SELECT * FROM approvals WHERE id = ?", (cur.lastrowid,)).fetchone()
    return {"ok": True, "approval": dict(row), "message": "Waiting for human approval. Nothing was paid."}


def _cash_row(conn: sqlite3.Connection, account: str):
    return conn.execute("SELECT * FROM cash_accounts WHERE name = ?", (account,)).fetchone()


def _duplicate(conn: sqlite3.Connection, kind: str, ref_id: int) -> dict | None:
    row = conn.execute(
        "SELECT * FROM approvals WHERE kind = ? AND ref_id = ? AND status IN ('pending', 'approved')",
        (kind, ref_id),
    ).fetchone()
    return dict(row) if row else None


@mcp.tool
def request_payment_approval(
    kind: Literal["invoice_payment", "rent_payment"],
    ref_id: int,
    reason: str,
    requested_by: str,
    ticket_id: int | None = None,
    account: str = "checking",
) -> dict:
    """Ask a human to approve paying a vendor invoice (ref_id = invoice id) or rent (ref_id = lease id).

    The amount is taken from the invoices / leases table, never from the caller. Nothing is paid here:
    the request lands on the board as 'pending' until a human decides it.
    """
    with _connect() as conn:
        if _cash_row(conn, account) is None:
            return {"ok": False, "error": f"No cash account named {account!r}."}
        if dup := _duplicate(conn, kind, ref_id):
            return {"ok": False, "error": "An open request already exists for this item.", "approval": dup}
        if kind == "invoice_payment":
            inv = conn.execute("SELECT * FROM invoices WHERE id = ?", (ref_id,)).fetchone()
            if inv is None:
                return {"ok": False, "error": f"No invoice {ref_id}."}
            if inv["status"] == "paid":
                return {"ok": False, "error": f"Invoice {ref_id} is already paid."}
            return _insert_approval(
                conn, kind=kind, ticket_id=ticket_id, ref_id=ref_id, vendor_id=inv["vendor_id"],
                amount=inv["amount"], account=account, reason=reason, requested_by=requested_by,
            )
        lease = conn.execute("SELECT * FROM leases WHERE id = ?", (ref_id,)).fetchone()
        if lease is None:
            return {"ok": False, "error": f"No lease {ref_id}."}
        return _insert_approval(
            conn, kind=kind, ticket_id=ticket_id, ref_id=ref_id, amount=lease["monthly_rent"],
            account=account, reason=reason, requested_by=requested_by,
        )


@mcp.tool
def request_purchase_order(
    vendor_id: int,
    sku: str,
    size: str,
    qty: int,
    reason: str,
    requested_by: str,
    ticket_id: int | None = None,
    account: str = "checking",
) -> dict:
    """Ask a human to approve a restock purchase order. Cost = qty x pricing.unit_cost.

    Refused if the vendor still has an open unpaid invoice (it will not ship), or the SKU/size is unknown.
    """
    with _connect() as conn:
        vendor = conn.execute("SELECT * FROM vendors WHERE id = ?", (vendor_id,)).fetchone()
        if vendor is None:
            return {"ok": False, "error": f"No vendor {vendor_id}."}
        if open_inv := _open_invoices(conn, vendor_id):
            return {
                "ok": False,
                "error": f"{vendor['name']} will not ship new product while it has an open unpaid invoice.",
                "open_invoices": open_inv,
            }
        price = conn.execute("SELECT unit_cost FROM pricing WHERE sku = ?", (sku,)).fetchone()
        stock = conn.execute(
            "SELECT 1 FROM inventory WHERE sku = ? AND size = ?", (sku, size)
        ).fetchone()
        if price is None or stock is None:
            return {"ok": False, "error": f"Unknown SKU/size {sku} {size}."}
        if qty <= 0:
            return {"ok": False, "error": "qty must be positive."}
        if _cash_row(conn, account) is None:
            return {"ok": False, "error": f"No cash account named {account!r}."}
        result = _insert_approval(
            conn, kind="purchase_order", ticket_id=ticket_id, ref_id=vendor_id, vendor_id=vendor_id,
            sku=sku, size=size, qty=qty, amount=round(qty * price["unit_cost"], 2), account=account,
            reason=reason, requested_by=requested_by,
        )
        result["vendor_lead_days"] = vendor["lead_days"]
        return result


@mcp.tool
def list_approvals(status: Literal["pending", "approved", "rejected", "paid", "all"] = "all") -> list[dict]:
    """List payment / purchase-order requests on the board (approvals table) with their status."""
    with _connect() as conn:
        if status == "all":
            rows = conn.execute("SELECT * FROM approvals ORDER BY id").fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM approvals WHERE status = ? ORDER BY id", (status,)
            ).fetchall()
        return [dict(r) for r in rows]


@mcp.tool
def decide_approval(
    approval_id: int, decision: Literal["approved", "rejected"], decided_by: str, note: str = ""
) -> dict:
    """HUMAN ONLY. Record a person's decision on a pending request. Never exposed to agents."""
    with _connect() as conn:
        row = conn.execute("SELECT * FROM approvals WHERE id = ?", (approval_id,)).fetchone()
        if row is None:
            return {"ok": False, "error": f"No approval {approval_id}."}
        # A human may still cancel an approved request that could not be paid (e.g. cash was short).
        if row["status"] != "pending" and not (row["status"] == "approved" and decision == "rejected"):
            return {"ok": False, "error": f"Approval {approval_id} is already {row['status']}."}
        conn.execute(
            "UPDATE approvals SET status = ?, decided_by = ?, decided_at = ?, decision_note = ? WHERE id = ?",
            (decision, decided_by, _now(), note, approval_id),
        )
        return {"ok": True, "approval": dict(conn.execute(
            "SELECT * FROM approvals WHERE id = ?", (approval_id,)).fetchone())}


@mcp.tool
def pay_approved(approval_id: int) -> dict:
    """Pay a human-approved request: deduct cash, log it in payments, and update the invoice / lease.

    Refuses if the request is not approved by a human, or if the cash account would go negative.
    Invoice -> status 'paid'. Rent -> lease.next_due moves one month. Purchase order -> paid to vendor
    (stock arrives after the vendor's lead_days; inventory is not changed until then).
    """
    with _connect() as conn:
        row = conn.execute("SELECT * FROM approvals WHERE id = ?", (approval_id,)).fetchone()
        if row is None:
            return {"ok": False, "error": f"No approval {approval_id}."}
        if row["status"] != "approved" or not row["decided_by"]:
            return {"ok": False, "error": f"Refused: approval {approval_id} is {row['status']}, not approved by a human."}
        cash = _cash_row(conn, row["account"])
        if cash is None:
            return {"ok": False, "error": f"No cash account named {row['account']!r}."}
        if cash["balance"] < row["amount"]:
            return {
                "ok": False,
                "error": f"Refused: not enough cash. {row['account']} has {cash['balance']:.2f}, "
                f"payment needs {row['amount']:.2f}.",
            }
        if row["kind"] == "purchase_order" and _open_invoices(conn, row["vendor_id"]):
            return {"ok": False, "error": "Refused: vendor has an open unpaid invoice and will not ship."}

        today = _today(conn)
        new_balance = round(cash["balance"] - row["amount"], 2)
        conn.execute(
            "UPDATE cash_accounts SET balance = ?, date = ? WHERE name = ?",
            (new_balance, today, row["account"]),
        )
        kind = {"invoice_payment": "invoice", "rent_payment": "rent", "purchase_order": "purchase_order"}[row["kind"]]
        cur = conn.execute(
            "INSERT INTO payments (kind, ref_id, amount, account, paid_at, approved_by) VALUES (?, ?, ?, ?, ?, ?)",
            (kind, row["ref_id"], row["amount"], row["account"], today, row["decided_by"]),
        )
        effect = {}
        if row["kind"] == "invoice_payment":
            conn.execute("UPDATE invoices SET status = 'paid' WHERE id = ?", (row["ref_id"],))
            effect = {"invoice_id": row["ref_id"], "invoice_status": "paid"}
        elif row["kind"] == "rent_payment":
            conn.execute(
                "UPDATE leases SET next_due = date(next_due, '+1 month') WHERE id = ?", (row["ref_id"],)
            )
            effect = {"lease_id": row["ref_id"], "next_due": conn.execute(
                "SELECT next_due FROM leases WHERE id = ?", (row["ref_id"],)).fetchone()["next_due"]}
        else:
            lead = conn.execute(
                "SELECT lead_days FROM vendors WHERE id = ?", (row["vendor_id"],)
            ).fetchone()["lead_days"]
            effect = {"expected_arrival": conn.execute(
                "SELECT date(?, '+' || ? || ' days') AS d", (today, lead)).fetchone()["d"]}
        conn.execute("UPDATE approvals SET status = 'paid' WHERE id = ?", (approval_id,))
        return {
            "ok": True,
            "payment_id": cur.lastrowid,
            "amount": row["amount"],
            "account": row["account"],
            "balance_after": new_balance,
            **effect,
        }


# ---------------------------------------------------------------- board


@mcp.tool
def draft_customer_message(
    recipient: str, subject: str, body: str, written_by: str, ticket_id: int | None = None
) -> dict:
    """Save a message draft on the board (drafts table). It is never emailed or sent to anyone."""
    with _connect() as conn:
        cur = conn.execute(
            "INSERT INTO drafts (ticket_id, recipient, subject, body, written_by, status, created_at) "
            "VALUES (?, ?, ?, ?, ?, 'draft', ?)",
            (ticket_id, recipient, subject, body, written_by, _now()),
        )
        return {"ok": True, "draft_id": cur.lastrowid, "status": "draft", "sent": False}


@mcp.tool
def list_drafts(ticket_id: int | None = None) -> list[dict]:
    """List message drafts on the board (drafts table), optionally for one ticket."""
    with _connect() as conn:
        if ticket_id is None:
            rows = conn.execute("SELECT * FROM drafts ORDER BY id").fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM drafts WHERE ticket_id = ? ORDER BY id", (ticket_id,)
            ).fetchall()
        return [dict(r) for r in rows]


@mcp.tool
def update_ticket(
    ticket_id: int,
    status: Literal["open", "in_progress", "waiting_approval", "blocked", "resolved"],
    note: str,
) -> dict:
    """Set a ticket's status and append a dated note to tickets.notes (keeps the original text)."""
    with _connect() as conn:
        row = conn.execute("SELECT * FROM tickets WHERE id = ?", (ticket_id,)).fetchone()
        if row is None:
            return {"ok": False, "error": f"No ticket {ticket_id}."}
        notes = (row["notes"] or "") + f"\n[{_today(conn)} {status}] {note}"
        conn.execute(
            "UPDATE tickets SET status = ?, notes = ? WHERE id = ?", (status, notes.strip(), ticket_id)
        )
        return {"ok": True, "ticket_id": ticket_id, "status": status}



if __name__ == "__main__":
    mcp.run(show_banner=False)
