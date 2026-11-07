"""Command-line runner: let the agent team work tickets.

    python backend/run_tickets.py --ticket 102          # one ticket on the current working DB
    python backend/run_tickets.py --all --reset         # reset the working DB, then every open ticket
"""

from __future__ import annotations

import argparse
import asyncio

from agents import pretty, run_ticket
from mcp_tools import mcp_client
from reset_db import reset_working_db


async def open_ticket_ids() -> list[int]:
    async with mcp_client() as client:
        result = await client.call_tool("list_open_tickets", {})
    return [t["id"] for t in result.structured_content["result"]]


async def main() -> None:
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--ticket", type=int, action="append", help="ticket id (repeatable)")
    group.add_argument("--all", action="store_true", help="every open ticket")
    parser.add_argument("--reset", action="store_true", help="reset the working DB first")
    args = parser.parse_args()

    if args.reset:
        reset_working_db()
        print("Working DB reset from the original.")
    ids = await open_ticket_ids() if args.all else args.ticket
    for ticket_id in ids:
        print(f"\n=== Ticket {ticket_id} ===")
        print(pretty(await run_ticket(ticket_id)))


if __name__ == "__main__":
    asyncio.run(main())
