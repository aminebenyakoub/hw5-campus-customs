# Campus Customs: multi-agent shop operations (HW5)

An agent team runs a small campus merch shop. Tickets land on a board (customer orders, rent, unpaid bills,
discount requests). Five agents work them through an MCP server that is their only access to the shop database,
and a human watches and approves payments on a React dashboard.

- **MCP server** (`MCP_server/`, FastMCP): 20 tools over `data/campus_customs_new.db`.
- **Backend** (`backend/`, FastAPI + Pydantic AI): Boss, Inventory, Accounting, Facilities and Customer Service. Any
  agent can delegate to any other. Every agent step is appended to `output/audit_trail.json`.
- **Dashboard** (`frontend/`, React + Vite + TypeScript): ticket board, live agent floor and log, approvals inbox,
  cash meter.
- **Model:** every agent uses **GPT-6 Luna through Portkey** (`gpt-6-luna`), and no other model.

Full reference: [`output/harness.md`](output/harness.md). Plan vs actual, cash and reflection:
[`output/desk_tickets.html`](output/desk_tickets.html).

## Layout

```
.
├── AI_prompts.md            prompt log, one section per problem
├── README.md
├── requirements.txt         Python dependencies
├── .env.example             copy to .env and add your Portkey key (.env is git-ignored)
├── .gitignore
├── .mcp.json                registers the MCP server for Claude Code
├── data/
│   ├── campus_customs.db       original shop database (never modified, the reset point)
│   └── campus_customs_new.db   working copy (the state after the graded full run: checking $160)
├── MCP_server/
│   ├── server.py
│   └── readme.md
├── backend/
│   ├── main.py              FastAPI routes
│   ├── agents.py            the five Pydantic AI agents + delegate tool
│   ├── models.py            data types
│   ├── mcp_tools.py         MCP connection, filtered per agent
│   ├── config.py · audit.py · reset_db.py · run_tickets.py
│   └── prompts/             boss.md, inventory.md, accounting.md, facilities.md, customer_service.md, shop_rules.md
├── frontend/                React desk
└── output/
    ├── harness.md · MCP_smoke.json · desk_tickets.html · design.md
    ├── resolved_tickets.json · resolved_board.html (+ screenshots/) · audit_trail.json
    └── GitHub_URL.txt
```

## Setup (once)

Needs Python 3.12+ and Node 20+.

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env          # then put your PORTKEY_API_KEY in .env
cd frontend && npm install && cd ..
```

## 1. Copy the original DB to the working copy (clean run)

The repo ships the working copy in its post-run state, so it matches the outputs. To start fresh, copy the original
over it. The original is never written.

```bash
cp data/campus_customs.db data/campus_customs_new.db
```

`.venv/bin/python backend/reset_db.py`, the dashboard's **Reset shop** button and `POST /api/reset` do the same
thing. The audit trail is never wiped.

## 2. Start the MCP server

The backend starts the MCP server for you, over stdio, for every agent run. To run it on its own:

```bash
.venv/bin/python MCP_server/server.py
```

To use it from Claude Code, open this folder in Claude Code and approve `campus-customs` from `.mcp.json`.

## 3. Start the FastAPI backend

```bash
cd backend
../.venv/bin/uvicorn main:app --reload --port 8000
```

The API is at http://localhost:8000, with interactive docs at http://localhost:8000/docs.

## 4. Start the React board

In a second terminal:

```bash
cd frontend
npm run dev
```

This opens http://localhost:5173. Pick a ticket, click **Run the agent team**, watch the agents, then **Approve &
pay** any request. The board calls the backend at http://localhost:8000 (override with `VITE_API_URL`).

## 5. Reset the DB before a full three-ticket run

Always start a full run from the original values:

1. Click **Reset shop** on the board, or run `cp data/campus_customs.db data/campus_customs_new.db`. Checking goes
   back to **$3,400**.
2. Run tickets 101, 102 and 103 from the board, approving payments when asked.

Or run it headless from the command line. This resets, then runs every open ticket. Payments still wait for a
human approval on the board.

```bash
.venv/bin/python backend/run_tickets.py --all --reset
```

## Shop rules (enforced in code)

- `desk.date_today` (2026-08-31) is today for the shop. Vendor lead times come from `vendors`.
- A vendor with an open unpaid invoice won't ship, so purchase orders to it are refused.
- Every payment needs human approval. Agents can only request. `pay_approved` refuses anything unapproved, and
  refuses if cash would go negative. Cash only goes out.
- No customer emails and no vendor calls. Drafts stay on the board.

## Graded run result

The full run started from a reset, with tickets run in the order 102, 101, 103: **$3,400.00 − $2,400.00 (rent) −
$840.00 (invoice 501) = $160.00**. This matches `cash_accounts` in `data/campus_customs_new.db`. All three tickets
are resolved. See `output/desk_tickets.html` (Cash tab) and `output/resolved_tickets.json`.
