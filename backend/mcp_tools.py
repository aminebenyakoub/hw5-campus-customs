"""The agents' only access to shop data: the campus-customs MCP server, filtered per agent.

There is no other shop-tools layer. Each agent sees just the MCP tools its role needs; `decide_approval`
is for humans only and is never given to any agent.
"""

from __future__ import annotations

import sys

from fastmcp import Client
from fastmcp.client.transports import StdioTransport
from pydantic_ai.mcp import MCPToolset

from config import MCP_SERVER, ROOT, WORKING_DB
from models import AgentName

HUMAN_ONLY_TOOLS = {"decide_approval"}

READ_CONTEXT = {"get_shop_date", "get_ticket"}

AGENT_TOOLS: dict[AgentName, set[str]] = {
    "boss": READ_CONTEXT | {"list_open_tickets", "update_ticket", "list_approvals", "list_drafts"},
    "inventory": READ_CONTEXT
    | {"check_stock", "list_inventory", "list_vendors", "get_sku_pricing", "request_purchase_order"},
    "accounting": READ_CONTEXT
    | {
        "get_cash_balance",
        "list_invoices",
        "list_vendors",
        "get_sku_pricing",
        "quote_discount",
        "get_lease_rent_due",
        "request_payment_approval",
        "request_purchase_order",
        "list_approvals",
        "pay_approved",
    },
    "facilities": READ_CONTEXT | {"get_lease_rent_due", "get_cash_balance", "list_approvals"},
    "customer_service": READ_CONTEXT
    | {"check_stock", "get_sku_pricing", "quote_discount", "draft_customer_message", "list_drafts"},
}

assert not any(tools & HUMAN_ONLY_TOOLS for tools in AGENT_TOOLS.values())


def mcp_client() -> Client:
    """A FastMCP client that launches MCP_server/server.py over stdio against the working DB."""
    return Client(
        StdioTransport(
            command=sys.executable,
            args=[str(MCP_SERVER)],
            env={"CAMPUS_DB_PATH": str(WORKING_DB)},
            cwd=str(ROOT),
        )
    )


def build_toolset() -> MCPToolset:
    return MCPToolset(mcp_client(), id="campus-customs")


def tools_for(toolset: MCPToolset, agent: AgentName):
    allowed = AGENT_TOOLS[agent]
    return toolset.filtered(lambda ctx, tool_def: tool_def.name in allowed)
