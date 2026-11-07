# Campus Customs Desk — dashboard design

`frontend/` · React + Vite + TypeScript · `npm run dev` → http://localhost:5173 (talks to the FastAPI backend at
http://localhost:8000, set in `frontend/src/api.ts`, override with `VITE_API_URL`).

## The idea

A real shop desk, not an admin console. The page should feel like sitting at a counter on Chapel Street: tickets
pinned on the left, your staff at their desks in the middle, the cheque book on the right. The agents do the
legwork; the human's job is the one thing they can't do, which is signing for money. Everything on the page makes
that split obvious.

## Layout (three columns, one top bar)

| Area | What lives there | Why |
|---|---|---|
| **Top bar** | Brand, shop date (2026-08-31 from `desk`), model (`gpt-6-luna`), approver name, Reset shop, and the **cash meter** | The two facts every decision depends on, which are "what day is it for the shop" and "how much money do we have", are always visible. |
| **Left: Ticket board** | The three tickets as cards with type icon, requester and a status pill | Picking work should be one click. Each card shows its state at a glance. |
| **Center: the floor** | Selected ticket header with **Run the agent team**, the **agent floor** (five desks), then the **live log** | This is where you watch. The desks say *who* is working; the log says *exactly what* they did. |
| **Right: the human's side** | **Needs your approval** inbox, **Who did what** summary, **Drafts on the board** | Everything that waits on a person sits in one column, and the approve button is always within reach. |

At 1180px the right column drops under the work area, and at 760px everything stacks, so it works on a laptop or a
phone.

## How the agents read differently

- **One colour and one glyph per agent**, used everywhere they appear (desk, log rows, summary chips, "prepared
  by"): Boss ★ navy, Inventory ▦ teal, Accounting $ green, Facilities ⌂ terracotta, Customer Service ✉ plum. After
  a minute you read the log by colour without reading names.
- **The Boss's desk spans the full width** above the four specialists. That's the org chart, so it's clear who
  routes and who works.
- **Desks have states.** An agent nobody called stays greyed out ("Not called"). An agent working has a pulsing dot
  and a soft glow. The agent producing the latest event lifts slightly ("speaking"). Each desk shows a plain-language
  activity line ("Using check_stock", "Asked Accounting", "Done"), a "via Boss" tag showing who delegated to it, and
  a speech bubble with its latest words.
- **The log is indented by delegation depth.** Boss → Facilities → Accounting reads as a nested conversation.
  Delegations show as **Boss → Accounting: task**. Tool calls are monospace chips in the agent's colour with their
  arguments, tool results are a muted one-line preview, and what an agent *said* sits in a chat bubble. Empty "I'm
  calling tools" messages are hidden, so only real words show up as speech.
- **Who did what** gives each agent that took part one line: the tools it used, who it asked for help, and its
  answer. Boss's final call and next steps go on top. A footer shows the token count and which agents were *not*
  called, which tells you whether the routing was focused.

## How resolved tickets show up

- Status pills use plain words instead of database values: *Open*, *In progress*, *Needs approval* (amber),
  *Blocked* (red), *Resolved* (green). While a run is going, the card's pill becomes a navy **● Agents working**.
- When a ticket resolves, a green **RESOLVED** rubber stamp thumps onto its card (a short scale-down animation) and
  the subject gets a soft strike-through, like paperwork that's done.
- Resolution rule (backend): a ticket is marked resolved when the run finishes and nothing is waiting on a human.
  If the agents filed a payment request, the ticket stays *Needs approval* until a human approves it, and then it
  resolves. A toast says which one happened.

## How cash shows up

- The **cash meter** is a navy "cheque book" block in the top bar with the checking balance in a large serif figure.
- It **counts down** (900 ms ease-out) when money leaves, and a red **−$2,400.00** tag drops off the number, so a
  payment feels like a payment.
- A thin bar under the number splits the balance into *free* and *held* (hatched brass) money, meaning money agents
  have already asked for. The line under it reads "$3,240 waiting on approval · $160 if all paid". That makes
  the shop's real constraint visible before anyone clicks approve.
- Each approval card shows the amount large, what it pays (invoice #501, lease #1, or qty × SKU size), the agent's
  reason, who prepared it, and **"checking after: $X"**. If the request is bigger than the balance, the card turns
  red and says the pay tool will refuse it.
- **Approve & pay as Amine** is the only button on the page that moves money. Paid and rejected requests drop into
  a small ledger below with the amount in red.

## Creative choices that make it pleasant to use

- **Warm paper, not grey SaaS.** Cream background, navy ink, a brass accent and Fraunces (a warm serif) for headings
  and money give it a campus-shop / Yale feel. Inter keeps body text easy to read, and JetBrains Mono makes tool calls
  look like the code they are.
- **Drafts look like letters**: ruled paper, the recipient at the top, and a dashed "DRAFT · NOT SENT" stamp. You
  can see at a glance that nothing went out.
- **Things arrive.** New log rows and approval cards slide in, and approvals show up *while* the agents are still
  working, so you can watch Accounting file a request in real time.
- **Toasts talk like a colleague**: "Boss picked up ticket #102.", "Paid $2,400.00. Checking is now $1,000.00.",
  "Nothing else waiting, so the ticket is resolved."
- **Approver name** is editable and remembered in the browser, so payments are signed by a real person. The name is
  stored in `payments.approved_by`.
- **Safe by default**: Reset asks for confirmation and is disabled during a run, and only one run can happen at a
  time. If the backend is down, a red banner shows the exact command to start it.
- **Light and dark mode** follow the system. Motion is turned off for people who ask their OS for reduced motion.

## Data flow

Every 8 s the board refreshes tickets, cash, approvals and drafts. During a run it polls every second:
`/api/events?after=<last index>&ticket_id=…` for new agent steps and `/api/runs/{run_id}` for status. Approvals
and cash also refresh mid-run so requests show up as soon as an agent files them. If the page is reloaded mid-run,
it picks the run back up from `/api/runs`. The ticket's history comes from the append-only audit trail, so older runs
(including CLI runs) can still be viewed. The log shows the latest run and the header says "latest of N".
