# Campus Customs MCP server

**What it is for.** This MCP server is the agent team's only door into the shop's data. Boss, Inventory,
Accounting, Facilities and Customer Service all call these tools instead of touching the database directly, so
every answer they give comes from the database and nothing is invented. More tools (e.g. vendor checks, payments)
can be added in later problems.

**Database.** `data/campus_customs_new.db` — the working copy. The original `data/campus_customs.db` is never
touched; copy it over the working copy to reset. The path can be overridden with the `CAMPUS_DB_PATH` environment
variable.

**Built with** [FastMCP](https://gofastmcp.com) (`server.py`).

## Tools

| Tool | Reads / writes | Returns / does |
|---|---|---|
| `get_shop_date()` | `desk` | The shop's today and desk notes. |
| `list_open_tickets()` | `tickets` | Every unresolved ticket. |
| `list_tickets()` | `tickets` | Every ticket with an `is_resolved` flag. |
| `get_ticket(ticket_id)` | `tickets` | One ticket. |
| `update_ticket(ticket_id, status, note)` | writes `tickets` | Sets status, appends a dated note. |
| `check_stock(sku, size)` | `inventory` | On-hand qty, location, `in_stock`; sizes on record if the size doesn't exist. |
| `list_inventory(sku?)` | `inventory` | All sizes of a SKU (or all rows). |
| `list_vendors()` | `vendors`, `invoices`, `desk` | Specialty, lead days, open invoices, `can_ship_new_product`, arrival date if ordered today. |
| `get_sku_pricing(sku)` | `pricing` | Unit cost, list price, margin per unit and margin %. |
| `quote_discount(sku, qty, discount_pct)` | `pricing` | Discounted unit price, order revenue / cost / margin, `sells_at_loss`. |
| `get_cash_balance()` | `cash_accounts`, `approvals` | Balance per account and money already requested. |
| `list_invoices(status)` | `invoices`, `vendors`, `desk` | Invoices with days overdue. |
| `get_lease_rent_due(lease_id)` | `leases`, `desk` | Landlord, rent, next due, days until due, overdue flag. |
| `request_payment_approval(kind, ref_id, ...)` | writes `approvals` | Pending request to pay an invoice or rent; amount taken from the DB. |
| `request_purchase_order(vendor_id, sku, size, qty, ...)` | writes `approvals` | Pending restock request; refused if the vendor has an unpaid invoice. |
| `list_approvals(status)` | `approvals` | Requests and their status. |
| `decide_approval(approval_id, decision, decided_by)` | writes `approvals` | **Human only** — never given to agents. |
| `pay_approved(approval_id)` | writes `cash_accounts`, `payments`, `invoices` / `leases`, `approvals` | Pays an approved request; refuses if not approved or cash would go negative. |
| `draft_customer_message(recipient, subject, body, ...)` | writes `drafts` | Saves a draft on the board. Never sent. |
| `list_drafts(ticket_id?)` | `drafts` | Drafts on the board. |

`approvals` and `drafts` are created in the working copy on first use; the original database never changes.

## Run

```bash
pip install fastmcp
python MCP_server/server.py
```
