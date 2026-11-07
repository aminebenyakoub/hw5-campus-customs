# AI Prompts Log — Campus Customs Multi-Agent Operations

Log of the vibe-coder prompts given to the AI coding assistant (Claude Code) for this homework.
One section per problem, each with the initial prompt and any follow-up prompts.

## Setup — project brief

**Prompt:**
> Today we are building a Campus Customs multi-agent operations, an agentic team that runs the shop. Open tickets
> land on a board: customer orders, rent, unpaid bills, discount requests, and whatever the shop has to handle. We will
> build three pieces that talk to each other: an MCP server, a FastAPI backend with a multi-agent team, and a React
> dashboard where a human can watch the agents at work and approve requests. The agent team has full connectivity: any
> agent may delegate tasks to any other agent. Agents: Boss (reads each ticket, routes it, makes final calls),
> Inventory (stock by SKU and size, shortfalls, which vendor can restock), Accounting (cash, invoices, margins,
> prepares payments / purchase orders for human approval), Facilities (lease, rent), Customer Service (drafts
> customer messages).
>
> The original shop database is in `data/` (tables: desk, tickets, inventory, pricing, vendors, leads,
> cash_accounts, payments, invoices). Tools update the database as tickets get resolved. Make a working copy
> `data/campus_customs_new.db` and point the MCP server and backend at it; keep the original untouched so it can be
> reset. Shop rules: `desk.date_today` is today for the shop and decides what is overdue; vendor lead times come from
> the vendors table; a vendor will not ship new products while it has an open unpaid invoice; human approval is
> required for any payment, and paying updates the relevant tables; the pay tool refuses if cash is short (no
> negative balances); cash only goes out, no revenue is modeled; reset the database before a full run; never email
> customers or call real vendors — drafts stay on the board.
>
> Use my Portkey API key for AI calls, and only GPT-6 Luna through Portkey for every agent — no other model in the
> code or the runs. Fetch the key from the `.env` used for earlier homeworks in the parent folder. Final submission is
> a public GitHub repo. Prompts will come one at a time titled Problem 1 … Problem 11. Create `AI_prompts.md` and
> update it as we work, one section per problem with its number and title, the prompt and follow-up prompts.

**Done:** copied the Portkey key into a git-ignored `homework 5/.env` (`MODEL_NAME=gpt-6-luna`), added
`.env.example` and `.gitignore`, created this log.

## Problem 2 — Study the Campus Customs database

**Prompt:**
> Problem 2: Study the campus customs database. Open data/compass_customs.db and look through every table and its
> fields. Copy the original file to data/compass_customs_new.db. Later problems update this working copy. Start
> output/harness.md. For each table, list the fields and one short line on why that table matters for the agents. We
> will keep growing this harness file in later problems.

**Done:** inspected all 9 tables (schema + rows); the real file is `data/campus_customs.db`, so the working copy is
`data/campus_customs_new.db` (identical checksum). Started `output/harness.md` with a table of fields and why each
table matters, plus the starting state and the 3 open tickets.

## Problem 3 — Build the MCP server

**Prompt:**
> Problem 3: Build the MCP server. Write an MCP server in MCP_server/ using fastMCP. It will talk to
> data/campus_customs_new.db. You do not need to connect it or run it in this problem. Every agent in this homework
> uses the tools in this MCP server. We will add more tools to it later. For now, write three tools you know you will
> need for the tickets in the database. Keep the names clear. Never invent any data and only use information in the
> database. In output/harness.md, list each of your three MCP tools. For every tool, include: which table it reads,
> which ticket it helps unlock (101, 102, or 103), one sentence on why that tool is the right one for that ticket.
> Avoid vague lines such as "reads inventory." Tie the tool to the ticket. Also add a short MCP_server/readme.md file
> that explains what the MCP server is for, which database file it uses, and the three tools it has.

**Done:** `MCP_server/server.py` with `check_stock` (101), `get_lease_rent_due` (102), `get_sku_pricing` (103);
`MCP_server/readme.md`; harness section 2. Tools return "not found" instead of guessing. Smoke-tested in memory
with the FastMCP client; working DB unchanged.

## Problem 4 — Add the MCP server to the VibeCoder and test each tool

**Prompt:**
> Problem 4: Add the MCP server to VibeCoder and test each tool. Add your MCP server to this project so the
> VibeCoder can call the tools. Save the connection JSON text in .mcp.json at the project root, or however you save
> the local MCP server list. When you are connected, test each of our three MCP tools. Save the evidence in
> output/MCP_smoke.json. For every tool, include: the prompt we asked the VibeCoder, the tool name, the tool output,
> which must match values in data/campus_customs_new.db.

**Follow-up prompts:**
> I have restarted Claude, but there is nothing asking me to approve anything.
>
> Tool loaded.

**Done:** `.mcp.json` registers `campus-customs` (stdio, `.venv/bin/python MCP_server/server.py`). After the
restart the three tools were available in Claude Code with no approval prompt. Called `check_stock`,
`get_lease_rent_due` and `get_sku_pricing` through MCP for tickets 101/102/103, compared each output with a direct
SQL query on `data/campus_customs_new.db` (all match), and saved the evidence in `output/MCP_smoke.json`.

## Problem 5 — Build the agent team and grow MCP tools

**Prompt:**
> Problem 5: Build the agent team and grow MCP tools. Build the agentic team for campus customs using Pydantic AI:
> Boss, Inventory, Accounting, Facilities, and Customer Service. Include prompts, models, and agent loops so they can
> delegate work to each other with full connectivity. Put agent prompts in backend/prompts/ (one file per agent). Put
> data types in backend/models.py and the agent files under backend/ (your layout can vary as long as the five roles
> are clear). Use our Portkey API key, and only GPT-6 Luna for every agent. Add any tools the agents need to your MCP
> server so they can work on the open tickets. Shop facts come from the MCP server over data/campus_customs_new.db.
> Do not invent a second shop tools layer that bypasses MCP. Wire the agents so they append to
> output/audit_trail.json as they run: for each agent loop step, record enough to audit later. Append to this file
> and do not wipe it each round. In output/harness.md, list each agent and each MCP tool, including ones you add in
> this problem, along with which table the tool uses. Also add a short safety section: the guardrails a real business
> would want when agents touch real customers and real money, plus limits that keep token use in check. Update
> MCP_server/readme.md so the tool list matches what you have now.

**Done:** MCP server grown from 3 to 19 tools (approvals + drafts board tables, human-only `decide_approval`,
`pay_approved` with no-overdraft check). Backend: `config.py` (GPT-6 Luna via Portkey, limits), `models.py`,
`mcp_tools.py` (per-agent MCP tool filters), `agents.py` (5 Pydantic AI agents + `delegate` tool), `audit.py`
(append-only audit trail), `run_tickets.py`, `reset_db.py`, `prompts/` (one per agent + shop rules). Live test on
ticket 102: Boss → Facilities → Accounting, rent approval request pending, ticket set to `waiting_approval`; 41
audit events. Working DB reset afterwards; audit trail kept. Harness sections 3–6 and MCP readme updated.

## Problem 6 — Plan the three tickets

**Prompt:**
> Problem 6: Plan the three tickets. Before you wire the backend, write down what you expect the team to do on each
> open ticket. Build output/desk_tickets.html, a page we can double-click with one tab per ticket (101, 102, and
> 103). Also add MCP cache and reflection tabs for later problems. Leave them blank or with a "to be filled later"
> note for now. On each ticket tab, fill an expected section only (leave room for an actual section you will fill
> after you run the agents). For each ticket's expected section, write who the Boss should call first and why, all
> the agent delegations you expect, and which MCP tools you expect that run to use. Plans that send every specialist
> on every ticket are not what we are looking for. We will compare this plan to what actually happens when our
> agents resolve the three tickets.

**Done:** `output/desk_tickets.html` (self-contained, no internet needed) with tabs 101 / 102 / 103 / MCP cache /
Reflection. Expected plans: 101 Boss → Inventory first (→ Accounting for invoice 501, → Customer Service draft;
Facilities skipped); 102 Boss → Facilities first (→ Accounting rent approval; Inventory and Customer Service
skipped); 103 Boss → Accounting first (discount), then Inventory (8 of 20), then Customer Service draft; Facilities
skipped, no purchase order expected because of the cash and the blocked vendor. Each tab lists the expected MCP tools,
the tools that should NOT be used, and the expected end state. Actual sections are placeholders.

## Problem 7 — Backend routes

**Prompt:**
> Problem 7: Backend routes. Your React frontend dashboard needs a backend it can call. In backend/main.py, use
> FastAPI and add routes that do the following: return the 3 tickets and whether each is open or resolved; take a
> ticket ID and run your agent team on that ticket; return recent agent events (what each agent said and which tool
> they used), so the board can refresh; approve a payment or purchase after a human clicks approve (agents only
> prepare the payment, this route is what actually changes cash); return the current checking balance from
> cash_accounts; reset the database to the original values when you want to try a fresh run. From the backend/
> folder, start the server with `uvicorn main:app --reload --port 8000`; this turns on the backend at
> http://localhost:8000 and the frontend dashboard can call those routes. In output/harness.md, list each route in
> one line (what URL and what it does).

**Done:** `backend/main.py` with `/api/tickets`, `/api/tickets/{id}/run` (background run + `/api/runs/{run_id}`),
`/api/events`, `/api/approvals` + approve / reject, `/api/cash`, `/api/drafts`, `/api/reset`, `/api/health`. Added
MCP tool `list_tickets` (routes go through MCP too). Tested live: ran ticket 102 through the API (rent approval 1
pending), approved it as Amine → cash $3,400 → $1,000, payment row written, lease next_due → 2026-10-02; second
approve refused; reset restored $3,400. Harness section 7 lists the routes.

## Problem 8 — Agent dashboard

**Prompt:**
> Problem 8: Agent Dashboard. Build the frontend dashboard in frontend/ with React + Vite + TypeScript. The page
> should call the routes you built in Problem 7. At minimum, the board should: list all three tickets; let you pick
> one ticket and start the agent team on it; show each agent and what they are saying/doing while the ticket runs;
> mark a ticket resolved when the run finishes; show a short summary of what each agent did on that ticket; let a
> human approve a pay or purchase when asked; show the checking balance (it should drop after an approved payment).
> Make the dashboard look good. This is a real desk people would want to sit at, so put something that looks really
> good. Tell the frontend to talk to your backend at http://localhost:8000. On the backend allow the Vite page
> origin (usually http://localhost:5173) so the user is allowed to call those routes. Start the board with
> `npm run dev`. This opens React Desk in your browser so you can pick tickets and watch agents. Write
> output/design.md with what you chose for the dashboard look (layout, how agents read differently, how resolved
> tickets and cash show up, and why), including the creative choices that make it feel special and something
> humans would actually enjoy using.

**Follow-up prompts (backend startup, before this problem):**
> (ran) `cd backend && ../.venv/bin/uvicorn main:app --reload --port 8000` → "Address already in use"; then
> "cd: no such file or directory: backend" twice.

**Done:** `frontend/` (React 19 + Vite 8 + TS): ticket board, agent floor (5 colour-coded desks with live
status and speech bubbles), live log indented by delegation depth, "Who did what" summary, approvals inbox with
Approve & pay / Reject, a cash meter that counts down with a drop tag, drafts shown as letters, toasts, light and
dark mode. Backend: explicit CORS for http://localhost:5173, auto-resolve rule (`settle_ticket`), `POST
/api/tickets/{id}/resolve`, shop date in `/api/health`. Verified live in the browser: ran ticket 102 from the UI →
Boss → Facilities → Accounting, approval appeared mid-run → Approve & pay → checking $3,400 → $1,000, ticket stamped
RESOLVED. DB reset afterwards. `output/design.md` written.

## Problem 9 — Resolve the tickets

**Prompt:**
> Problem 9: Resolve the tickets. Before testing the agents on a full run over three tickets, reset the working
> database data/campus_customs_new.db again so you start clean. Note the starting checking balance. Then run all
> three tickets on the board (101, 102, 103) until each is resolved. Open output/desk_tickets.html from Problem 6. On
> each ticket tab, fill the actual section from this run: which agents worked, what they delegated, and which tools
> they used. Keep your expected section so you can compare the two. On the cash tab of the same
> output/desk_tickets.html, itemize the money: starting checking balance (after the reset); for each ticket, how cash
> changed when that ticket resolved and why (why pay/purchase, dollar amount); ending checking balance. It must
> match cash_accounts in the working database. Wrong cash math loses points even if the board shows every ticket
> resolved. Also save output/resolved_tickets.json with, for each ticket: ID, final status, short outcome, what each
> agent contributed, any human approvals. output/resolved_board.html: a page you can double-click with a screenshot
> of your React board for each resolved ticket (101, 102 and 103). Append real runs to output/audit_trail.json.
> Finish output/harness.md so it covers tables, MCP tools, the five agents, API routes, the dashboard, and safety
> rules.

**Done:** reset the working DB (start $3,400.00), then ran the tickets from the React desk. A board selection bug
(the URL hash didn't change the selected ticket) meant ticket 102 ran first; the order was 102 → 101 → 103.
Approved rent #1 (−$2,400) and invoice 501 #2 (−$840) as Amine; 103 needed no payment. All three resolved; ending
checking $160.00 = `cash_accounts`. Filled the Actual sections and turned the "MCP cache" tab into the **Cash** tab
(the Problem 6 "MT cache" meant cash). Wrote `output/resolved_tickets.json` and `output/resolved_board.html`
(screenshots embedded, PNGs in `output/screenshots/`). Audit trail now 504 events. Rewrote `output/harness.md` as
the full reference. Small fixes: rejecting a request now settles its ticket and can cancel an approved-but-unpaid
request, and the URL hash now selects the ticket.

## Problem 10 — Reflection

**Prompt:**
> Problem 10: Reflection. 1) Open output/desk_tickets.html and fill the reflection tab. 2) Tell me how you would
> evaluate the performance of the agents on each ticket and why. 3) For each ticket, how did the actual compare to
> the expected plan you wrote earlier? 4) What would have been simpler as one agent with tools, and why? 5) Describe
> three new problems Campus Customs might face that this agent team could resolve with the tools we built. 6) Tell me
> three new problems Campus Customs might face that this agent team could not resolve with the tools we built, and
> explain the tools and agents we would need to solve them. 7) Tie every answer to this app and the three tickets we
> ran. 8) Use the ticket tabs and cash tab on the same page as our evidence.

**Done:** filled the Reflection tab of `output/desk_tickets.html` with metrics computed from
`output/audit_trail.json`:
- **Evaluation:** a six-criterion method (money, rules, customer outcome, routing, cost, consistency) and a
  per-ticket scorecard: 101 B−, 102 A, 103 C+.
- **Plan vs actual:** a table per ticket.
- **One agent vs the team:** one agent would be simpler at this size (102: 5 of 10 tool calls were repeated
  context reads; 101: duplicate requests; 103: no single agent held both the $264 and $160 figures).
- **Three problems the team could solve:** a purchase order for 101's tee, a Crest Mug order through Elm City
  Gifts, a wrong or duplicate rent notice.
- **Three it couldn't:** accepting the club's order (needs a Sales agent, stock and receivables tools), a cash
  crunch (needs a Treasury agent with a forecast), email intake and time passing (needs Intake, a scheduler and a
  Comms agent).

In-page links jump to the Ticket and Cash tabs as evidence.

## Problem 11 — Submit to GitHub

**Prompt:**
> Okay, let's solve those three new problems that it can't solve and wrap up with Problem 11. Submit to GitHub as
> follows. Problem 11: Submit to GitHub. Push your code to a public GitHub repository so graders can clone it.
> Submit the repo URL to Canvas and also put it in output/GitHub_URL.txt. Do not push my real .env to the GitHub
> repo. Do include both database files under data/ (the original and our working copy) so graders can run the app
> easily. Expected layout: AI_prompts.md, requirements.txt, .env.example, .gitignore, .mcp.json, README.md,
> data/ (campus_customs.db, campus_customs_new.db), MCP_server/ (server.py, readme.md), frontend/, backend/ (main.py,
> models.py, prompts/ boss.md, inventory.md, accounting.md, facilities.md, customer_service.md), output/
> (harness.md, MCP_smoke.json, desk_tickets.html, design.md, resolved_tickets.json, resolved_board.html,
> audit_trail.json, GitHub_URL.txt). The README should explain: copy the original DB to the working copy when you
> need a clean run, start the MCP server, start the FastAPI backend, start the React board, reset the DB before a
> full ticket run.

**Follow-up prompt:**
> Wait, you scared me about the thing that the cash only goes out. You know what? Those three things, the three
> missing capabilities, let's just leave them alone and tackle Problem 11 the way I told you to.

**Done:** the extension work (sales/receivables, treasury forecast, intake/time/outbox) was started, then fully
reverted on request. Code, prompts and routes are back to the Problem 10 state (20 MCP tools, 5 agents), and the
empty extension tables were dropped from the working DB (checking still $160). Renamed this log to `AI_prompts.md`
to match the layout, wrote `README.md`, updated `.gitignore` (both DBs are committed, `.env` is not), checked that
the Portkey key appears in no committed file, pushed to a public repo and saved the URL in `output/GitHub_URL.txt`.
