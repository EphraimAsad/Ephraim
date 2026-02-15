"""
MCP (Model Context Protocol) Package

Provides integration with MCP servers for extending Ephraim
with external tools and capabilities.

MCP is an open protocol that allows AI assistants to connect
to external tools/servers via JSON-RPC.
"""

from .client import (
    MCPClient,
    MCPServer,
    MCPTool,
    get_mcp_client,
)

from .protocol import (
    JSONRPCRequest,
    JSONRPCResponse,
    JSONRPCError,
)

__all__ = [
    "MCPClient",
    "MCPServer",
    "MCPTool",
    "get_mcp_client",
    "JSONRPCRequest",
    "JSONRPCResponse",
    "JSONRPCError",
]
