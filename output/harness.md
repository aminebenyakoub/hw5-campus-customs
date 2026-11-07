# Campus Customs — Agent Harness

The harness is everything the agent team runs inside: the data, the tools, the agents, the API, the dashboard and the
rules that keep it safe. It was built over Problems 2–9.

```
 React desk (frontend/, :5173) ──HTTP──▶ FastAPI (backend/main.py, :8000)
                                            │  runs ▼                 │ approve / cash / reset
                                   Pydantic AI agent team             │
          Boss ⇄ Inventory ⇄ Accounting ⇄ Facilities ⇄ Customer Service (any agent may delegate to any other)
                                            │ MCP over stdio (only door to shop data)
                                   MCP_server/server.py (FastMCP, 20 tools)
                                            │ SQLite
                         data/campus_customs_new.db  ◀── reset copies ── data/campus_customs.db (never written)
          every agent step ──▶ output/audit_trail.json (append-only)
```

**Model:** every agent uses **GPT-6 Luna** (`gpt-6-luna`) through **Portkey**. The model is hard-coded in
`backend/config.py`, and the key comes from the git-ignored `.env`.

**Run it**

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
cd backend && ../.venv/bin/uvicorn main:app --reload --port 8000     # API
cd frontend && npm install && npm run dev                           # desk at http://localhost:5173
.venv/bin/python backend/run_tickets.py --all --reset              # or: headless run from the CLI
```

---

## 1. Database and tables

- **Original (read-only):** `data/campus_customs.db` is the reset point and is never written.
- **Working copy:** `data/campus_customs_new.db`. The MCP server, and through it the agents and the API, read and
  write only this file. **Reset** (`POST /api/reset`, `backend/reset_db.py`, or `run_tickets.py --reset`) copies the
  original over it.

| Table | Fields | Why it matters for the agents |
|---|---|---|
| `desk` | `date_today`, `notes` | The shop's "today" (2026-08-31). Every agent uses it to judge what's due or overdue. |
| `tickets` | `id`, `type`, `requester`, `subject`, `sku`, `size`, `qty`, `lease_id`, `invoice_id`, `status`, `notes`, `created_at` | The work queue. Boss reads and routes each ticket. Links point to the SKU, lease or invoice involved. Status and dated notes are written back as work happens. |
| `inventory` | `sku`, `name`, `size`, `qty`, `location` (PK `sku`+`size`) | Inventory checks stock per SKU and size to see whether an order can be filled. |
| `pricing` | `sku`, `unit_cost`, `list_price` | Accounting computes margins and the lowest discount that still makes money. |
| `vendors` | `id`, `name`, `specialty`, `lead_days` | Inventory picks who can restock and how long it takes. |
| `leases` | `id`, `space_name`, `landlord`, `monthly_rent`, `next_due`, `notes` | Facilities knows what rent is owed, to whom and when. Paying rent moves `next_due` one month. |
| `cash_accounts` | `name`, `balance`, `date` | The only money. It must never go negative, and only `pay_approved` lowers it. |
| `payments` | `id`, `kind`, `ref_id`, `amount`, `account`, `paid_at`, `approved_by` | The ledger of money out. Every row carries the human who approved it. |
| `invoices` | `id`, `vendor_id`, `amount`, `due_date`, `status`, `description` | Vendor bills. An open one blocks that vendor from shipping new product, and past-due ones are overdue. |
| `approvals` *(board table)* | `id`, `kind`, `ticket_id`, `ref_id`, `vendor_id`, `sku`, `size`, `qty`, `amount`, `account`, `reason`, `requested_by`, `status`, `decided_by`, `decided_at`, `decision_note`, `created_at` | Payment and purchase-order requests the agents prepare and humans decide (pending → approved / rejected → paid). |
| `drafts` *(board table)* | `id`, `ticket_id`, `recipient`, `subject`, `body`, `written_by`, `status`, `created_at` | Customer and requester messages. They always stay `draft` and are never sent. |

The two board tables are created by the MCP server in the working copy on first use. They're not in the original,
and a reset removes them. (The brief mentions a `leads` table; the real database has `leases`.)

**Starting state (shop date 2026-08-31):** checking **$3,400**. Invoice 501 to Bulldog Print Co is **$840, due
2026-08-28, 3 days overdue**, which blocks Bulldog. Lease 1 is $2,400 rent due 2026-09-02. `CC-TEE-WHITE` S = 0 and
`CC-HOOD-NAVY` M = 8. Vendors: Bulldog Print Co (apparel, 5 days), Elm City Gifts (mugs, 3 days), QuickShip CT
(courier, 1 day).

| Ticket | Ask | What makes it tricky |
|---|---|---|
| 101 `customer_order` · Tauhid Zaman | 1 × tee, size S | Out of stock, and the restock vendor is blocked by overdue invoice 501. |
| 102 `rent_notice` · Elm City Properties | Rent due in 2 days | $2,400 against lease 1. |
| 103 `price_override` · Yale AI Club | 20 hoodies M, bulk discount | Only 8 in stock. Margin is set by cost $22 / list $58. |

---

## 2. MCP server and tools

`MCP_server/server.py` (FastMCP) on `data/campus_customs_new.db`, override with `CAMPUS_DB_PATH`. It's registered
for the VibeCoder in `.mcp.json`, and the first three tools were smoke-tested through MCP (`output/MCP_smoke.json`).
The backend starts it over stdio (`backend/mcp_tools.py`). **It is the only door to shop data**, and there is no
second tools layer. Every tool answers from the database and says "not found" instead of guessing.

### The first three tools (Problem 3) and the ticket each unlocks

| Tool | Table it reads | Ticket | Why it's the right tool for that ticket |
|---|---|---|---|
| `check_stock(sku, size)` | `inventory` | **101**: 1 × `CC-TEE-WHITE` S | The order can only be promised if size S is on the shelf. It's at 0, which turns the ticket into a restock problem. |
| `get_lease_rent_due(lease_id)` | `leases` (+ `desk`) | **102**: lease 1 rent notice | Checks the emailed notice against the lease on file ($2,400 to Elm City Properties, due 2026-09-02), so the right amount goes to the right landlord. |
| `get_sku_pricing(sku)` | `pricing` | **103**: 20 × `CC-HOOD-NAVY` M | A discount needs a floor: $22 cost vs $58 list gives a $36 margin (62.1%), so any price above $22 still makes money. |

### All 20 tools

| Tool | Table(s) | R/W | Used for |
|---|---|---|---|
| `get_shop_date` | `desk` | R | The shop's today, for due and overdue. |
| `list_open_tickets` | `tickets` | R | Every unresolved ticket. |
| `list_tickets` | `tickets` | R | Every ticket with an `is_resolved` flag (dashboard). |
| `get_ticket` | `tickets` | R | One ticket. |
| `update_ticket` | `tickets` | W | Sets status and appends a dated note. |
| `check_stock` | `inventory` | R | On hand for one SKU and size. |
| `list_inventory` | `inventory` | R | All sizes of a SKU. |
| `list_vendors` | `vendors`, `invoices`, `desk` | R | Specialty, lead time, arrival date, and whether it can ship (no open invoice). |
| `get_sku_pricing` | `pricing` | R | Cost, list price, margin. |
| `quote_discount` | `pricing` | R | Discounted price, order margin, `sells_at_loss` flag. |
| `get_cash_balance` | `cash_accounts`, `approvals` | R | Balance plus money already requested. |
| `list_invoices` | `invoices`, `vendors`, `desk` | R | Open bills and days overdue. |
| `get_lease_rent_due` | `leases`, `desk` | R | Rent, landlord, due date, days left. |
| `request_payment_approval` | `approvals` (amount read from `invoices` / `leases`) | W | Puts an invoice or rent payment on the board for a human. Duplicates are refused. |
| `request_purchase_order` | `approvals` (checks `vendors`, `invoices`, `pricing`, `inventory`) | W | Restock request. Refused while the vendor has an unpaid invoice. |
| `list_approvals` | `approvals` | R | Pending, approved, rejected and paid requests. |
| `decide_approval` | `approvals` | W | **Human only.** Approve or reject. Not given to any agent. |
| `pay_approved` | `approvals`, `cash_accounts`, `payments`, `invoices`, `leases` | W | Pays a human-approved request. Refuses if it isn't approved or if cash would go negative. |
| `draft_customer_message` | `drafts` | W | Saves a reply on the board. Never sent. |
| `list_drafts` | `drafts` | R | Drafts on the board. |

---

## 3. The five agents

`backend/agents.py` (Pydantic AI). Prompts are in `backend/prompts/<agent>.md` plus the shared `shop_rules.md`, and
data types are in `backend/models.py`. **Agent loop:** model call → MCP tool calls → model call … until it answers.
**Full connectivity:** every agent has `delegate(to_agent, task)`, which runs the other agent's loop and returns its
answer. Boss returns a structured `TicketOutcome` (owner, status, decision, approval ids, draft ids, next steps).

| Agent | Job | MCP tools it may call (besides `get_shop_date`, `get_ticket`, `delegate`) |
|---|---|---|
| **Boss** | Reads each ticket, decides who works it, sets status, makes the final call. Has no stock or money tools, so it has to delegate. | `list_open_tickets`, `update_ticket`, `list_approvals`, `list_drafts` |
| **Inventory** | Stock by SKU and size, shortfalls, which vendor can restock and by when. | `check_stock`, `list_inventory`, `list_vendors`, `get_sku_pricing`, `request_purchase_order` |
| **Accounting** | Cash, invoices, margins, discounts. Prepares payments and purchase orders for human approval. | `get_cash_balance`, `list_invoices`, `list_vendors`, `get_sku_pricing`, `quote_discount`, `get_lease_rent_due`, `request_payment_approval`, `request_purchase_order`, `list_approvals`, `pay_approved` |
| **Facilities** | Lease, rent, shop space. Checks rent notices against the lease and asks Accounting to pay. | `get_lease_rent_due`, `get_cash_balance`, `list_approvals` |
| **Customer Service** | Drafts messages to customers and requesters. Never sends them. | `check_stock`, `get_sku_pricing`, `quote_discount`, `draft_customer_message`, `list_drafts` |

What they actually did in the full run (Problem 9): 102 was Boss → Facilities, then Accounting. 101 was
Boss → Inventory → Accounting, plus Boss → Accounting and Boss → Customer Service. 103 was Boss → Inventory,
Accounting and Customer Service. Facilities was used only on 102, and Customer Service only on the two customer
tickets. Details and plan-vs-actual are in `output/desk_tickets.html`.

---

## 4. API routes

`backend/main.py` (FastAPI) at `http://localhost:8000`, with interactive docs at `/docs`. CORS allows the Vite desk
(`http://localhost:5173`). Every shop read and write goes through the MCP server.

- `GET /api/health`: model, working database and shop date.
- `GET /api/tickets`: every ticket with its status and `state` (open or resolved).
- `POST /api/tickets/{ticket_id}/run`: starts the agent team on one ticket in the background and returns a `run_id`. One run at a time.
- `GET /api/runs` · `GET /api/runs/{run_id}`: run status (queued, running, done, error) and Boss's outcome.
- `POST /api/tickets/{ticket_id}/resolve`: a human marks a ticket resolved by hand.
- `GET /api/events?after=&limit=&ticket_id=&run_id=`: audit-trail events (what each agent said, which tool it used) for live refresh.
- `GET /api/approvals?status=`: requests the agents prepared.
- `POST /api/approvals/{approval_id}/approve`: a human approves, then this route pays. **The only route that lowers cash.**
- `POST /api/approvals/{approval_id}/reject`: a human rejects (also cancels an approved request that couldn't be paid). No money moves.
- `GET /api/cash`: checking balance from `cash_accounts`, plus requested-but-unpaid.
- `GET /api/drafts?ticket_id=`: drafts on the board.
- `POST /api/reset`: copies the original database over the working copy. The audit trail is kept.

**Ticket resolution rule:** when a run finishes, or a request for that ticket is paid or rejected, the backend sets
the ticket to `resolved` (via `update_ticket`) if nothing on it still waits on a human and Boss didn't mark it
`blocked`.

---

## 5. Dashboard

`frontend/` (React 19 + Vite + TypeScript), started with `npm run dev`, at `http://localhost:5173`. It calls the API at
`VITE_API_URL` (default `http://localhost:8000`). The layout has three columns:
- **Left:** the ticket board.
- **Centre:** the agent floor (five colour-coded desks that light up while working) and a live log indented by
  delegation depth.
- **Right:** the approvals inbox with Approve & pay / Reject, a "Who did what" summary, and drafts shown as
  unsent letters.
- **Top bar:** the cash meter counts down when money is paid.

`#101` in the URL selects that ticket. Design rationale is in `output/design.md`, and screenshots of the resolved
board are in `output/resolved_board.html`.

---

## 6. Audit trail

`output/audit_trail.json` is a JSON array that is **only ever appended to**. Reset never touches it, and it holds
every run so far, including the Problem 9 runs `21d5c16b`, `9f12a86e` and `63a08abf`.

There is one record per agent-loop step, with these fields:
- `ts`, `run_id`, `ticket_id`, `agent`, `depth`, and `chain` (who delegated to whom).
- `step` and `event`. `event` is one of `agent_start`, `model_response`, `tool_call`, `tool_result`,
  `delegation`, `agent_end` or `agent_error`.
- `model`.
- `detail`: the task, what the agent said, the tool and its args, the tool result, and the delegation target with
  accepted/refused and the reason.
- `input_tokens` and `output_tokens`.

Long text is clipped to 1,500 characters.

---

## 7. Safety rules

### Shop rules and where they are enforced

| Rule | Enforced in **code** (MCP server / backend) | Also in prompts |
|---|---|---|
| Facts only from the database | Every tool reads SQLite and returns "not found" instead of guessing. Amounts in requests are read from `invoices` / `leases` / `pricing`, never taken from the model. | `shop_rules.md` |
| `desk.date_today` is today | Overdue and days-until-due are computed from `desk`, not the real calendar. | `shop_rules.md` |
| Vendor lead times from `vendors` | `list_vendors` gives `lead_days` and the arrival date from the shop date. | Inventory prompt |
| No shipping while a vendor has an unpaid invoice | `request_purchase_order` and `pay_approved` refuse. `list_vendors` shows `can_ship_new_product`. | Inventory prompt |
| Human approval for every payment | `decide_approval` is in no agent's tool list (asserted in `mcp_tools.py`). `pay_approved` requires `status = approved` and a `decided_by`. The API approve route is the only way to approve. | Accounting prompt |
| Paying updates the tables | `pay_approved` lowers `cash_accounts`, inserts into `payments` (with `approved_by`), sets the invoice to `paid` or moves `leases.next_due`, and marks the approval `paid`. | — |
| No negative balances | `pay_approved` refuses if `balance < amount`. | Accounting prompt |
| Cash only goes out | No tool adds money. | `shop_rules.md` |
| Never email customers or call vendors | No send tool exists. Drafts stay `draft` on the board. | Customer Service prompt |
| Reset before a full run | `POST /api/reset`, `run_tickets.py --reset`. The original file is never opened for writing. | — |

### Guardrails a real business would want

- **Human approval for every dollar**, enforced in code rather than prompts. The person who approved is written
  to `payments.approved_by`.
- **Least privilege:** each agent sees only the tools its job needs. Boss can't move money, and Facilities and
  Customer Service can't request it.
- **Duplicate-request guard:** this stopped a second $840 request in the real run.
- **Nothing leaves the building:** drafts only.
- **Full append-only audit trail.**
- **Secrets:** stored only in a git-ignored `.env` (an `.env.example` is shipped). One model, hard-coded.
- **For production I'd add:** approval limits by amount, two-person sign-off for large payments, a daily spend
  cap, PII redaction in logs, a kill switch, and alerts on refused tool calls.

### Token limits

- **Model settings:** one cheap model (GPT-6 Luna), reasoning off, `max_tokens` 900 per call, temperature 0.2.
- **Per agent loop:** Pydantic AI `UsageLimits` caps Boss at 12 model calls and specialists at 8, with at most 12
  tool calls each.
- **Delegation limits:** depth ≤ 2, no delegating back to an agent already in the chain, ≤ 8 delegations and
  ≤ 120k tokens per ticket. Past those limits, `delegate` refuses and the agent answers with what it has.
- **Small prompts:** each agent only sees its own tools, and tool results are compact JSON.
- **Measured in the full run:** 102 used 18.3k in / 0.7k out, 101 used 31.5k / 1.6k, and 103 used 20.6k / 1.1k,
  for a total of **~70.4k input / 3.4k output tokens** across the three tickets.

---

## 8. Full run results (Problem 9)

The working database was reset, then the tickets were run from the React desk in the order 102, 101, 103. Amine
approved each payment on the board.

| | Change | Checking |
|---|---|---|
| Start (after reset) | n/a | **$3,400.00** |
| 102 resolved: rent, lease 1, approval #1 → payment #1 | −$2,400.00 | $1,000.00 |
| 101 resolved: overdue invoice 501 (Bulldog Print Co), approval #2 → payment #2 | −$840.00 | $160.00 |
| 103 resolved: discount recommendation only (15%), no purchase order | $0.00 | $160.00 |
| **End**: matches `cash_accounts.checking` = 160.0 | **−$3,240.00** | **$160.00** |

## 9. Output files

| File | What |
|---|---|
| `output/harness.md` | This document. |
| `output/MCP_smoke.json` | The first three MCP tools called through MCP and compared with SQL. |
| `output/desk_tickets.html` | Expected plan vs actual per ticket, the Cash tab, and the Reflection tab. |
| `output/resolved_tickets.json` | For each ticket: final status, outcome, each agent's contribution, human approvals. |
| `output/resolved_board.html` | Screenshots of the resolved React board (also in `output/screenshots/`). |
| `output/audit_trail.json` | Append-only record of every agent step. |
| `output/design.md` | Dashboard design choices. |
