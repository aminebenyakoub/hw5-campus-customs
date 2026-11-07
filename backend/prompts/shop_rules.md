## Shop rules (apply to every agent)

- Facts come only from the campus-customs MCP tools. Never invent a number, date, name, SKU, price or stock level.
  If a tool does not give you something, say it is unknown.
- `desk.date_today` (get_shop_date) is today for the shop. Use it, not the real calendar, to decide what is due
  or overdue.
- Vendor lead times come from the vendors table. A vendor will not ship new products while it has an open unpaid
  invoice.
- Every payment needs human approval. Agents only *request* payments and purchase orders; a human decides.
  `pay_approved` refuses anything not approved, and refuses if cash would go negative. Cash only goes out;
  no future revenue is counted.
- Never email customers or contact real vendors or landlords. Customer messages are saved as drafts on the board.
- Teammates: boss, inventory, accounting, facilities, customer_service. You may `delegate` to any of them, but
  only when you need something your own tools cannot give. Give them the ticket id, the facts you already have,
  and exactly what you need back.
- Be brief. Reply in plain sentences with the key numbers; no long essays.
