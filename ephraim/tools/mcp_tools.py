"""
MCP Tools

Provides tools for interacting with MCP servers.
"""

from typing import Optional, Dict, Any, List

from .base import BaseTool, ToolResult, ToolParam, ToolCategory, register_tool


# Lazy import MCP client to avoid circular imports
def _get_mcp_client():
    from ..mcp import get_mcp_client
    return get_mcp_client()


@register_tool
class MCPConnectTool(BaseTool):
    """
    Connect to an MCP server.

    MCP servers must be configured in Ephraim.md or mcp.json.
    """

    name = "mcp_connect"
    description = "Connect to a configured MCP server"
    category = ToolCategory.EXECUTION

    parameters = [
        ToolParam(
            name="server",
            type="string",
            description="Name of the MCP server to connect to",
            required=True,
        ),
    ]

    def execute(self, **params) -> ToolResult:
        """Connect to the server."""
        server_name = params["server"]
        client = _get_mcp_client()

        # Check if server is registered
        if server_name not in client.servers:
            available = list(client.servers.keys())
            return ToolResult.fail(
                f"Unknown server: {server_name}. "
                f"Available: {available or 'none (configure in Ephraim.md)'}"
            )

        try:
            success = client.connect(server_name)
            if success:
                tools = client.list_tools(server_name)
                return ToolResult.ok(
                    data={
                        "server": server_name,
                        "connected": True,
                        "tools": [t.name for t in tools],
                    },
                    summary=f"Connected to {server_name} ({len(tools)} tools available)",
                )
            else:
                return ToolResult.fail(f"Failed to connect to {server_name}")
        except Exception as e:
            return ToolResult.fail(f"Connection error: {str(e)}")


@register_tool
class MCPDisconnectTool(BaseTool):
    """Disconnect from an MCP server."""

    name = "mcp_disconnect"
    description = "Disconnect from an MCP server"
    category = ToolCategory.EXECUTION

    parameters = [
        ToolParam(
            name="server",
            type="string",
            description="Name of the MCP server to disconnect from",
            required=True,
        ),
    ]

    def execute(self, **params) -> ToolResult:
        """Disconnect from the server."""
        server_name = params["server"]
        client = _get_mcp_client()

        try:
            client.disconnect(server_name)
            return ToolResult.ok(
                data={"server": server_name, "connected": False},
                summary=f"Disconnected from {server_name}",
            )
        except Exception as e:
            return ToolResult.fail(f"Disconnect error: {str(e)}")


@register_tool
class MCPListToolsTool(BaseTool):
    """List available tools from MCP servers."""

    name = "mcp_list_tools"
    description = "List tools available from connected MCP servers"
    category = ToolCategory.READ_ONLY

    parameters = [
        ToolParam(
            name="server",
            type="string",
            description="Server name (optional, lists all if not specified)",
            required=False,
            default=None,
        ),
    ]

    def execute(self, **params) -> ToolResult:
        """List available tools."""
        server_name = params.get("server")
        client = _get_mcp_client()

        tools = client.list_tools(server_name)

        if not tools:
            return ToolResult.ok(
                data={"tools": []},
                summary="No MCP tools available (connect to a server first)",
            )

        tool_info = []
        for tool in tools:
            tool_info.append({
                "name": tool.name,
                "description": tool.description,
                "server": tool.server,
            })

        return ToolResult.ok(
            data={"tools": tool_info},
            summary=f"{len(tools)} MCP tools available",
        )


@register_tool
class MCPCallTool(BaseTool):
    """
    Call a tool on an MCP server.

    This allows Ephraim to use external tools provided by MCP servers.
    """

    name = "mcp_call"
    description = "Call a tool provided by an MCP server"
    category = ToolCategory.EXECUTION

    parameters = [
        ToolParam(
            name="server",
            type="string",
            description="MCP server name",
            required=True,
        ),
        ToolParam(
            name="tool",
            type="string",
            description="Tool name to call",
            required=True,
        ),
        ToolParam(
            name="arguments",
            type="dict",
            description="Tool arguments as a dictionary",
            required=False,
            default={},
        ),
    ]

    def execute(self, **params) -> ToolResult:
        """Call the MCP tool."""
        server_name = params["server"]
        tool_name = params["tool"]
        arguments = params.get("arguments", {})

        client = _get_mcp_client()

        # Check connection
        if server_name not in client.connections:
            return ToolResult.fail(
                f"Not connected to server: {server_name}. "
                f"Use mcp_connect first."
            )

        try:
            result = client.call_tool(server_name, tool_name, arguments)

            return ToolResult.ok(
                data={
                    "server": server_name,
                    "tool": tool_name,
                    "result": result,
                },
                summary=f"Called {tool_name} on {server_name}",
            )
        except Exception as e:
            return ToolResult.fail(f"Tool call failed: {str(e)}")


@register_tool
class MCPStatusTool(BaseTool):
    """Get status of MCP connections."""

    name = "mcp_status"
    description = "Get status of MCP server connections and available tools"
    category = ToolCategory.READ_ONLY

    parameters = []

    def execute(self, **params) -> ToolResult:
        """Get MCP status."""
        client = _get_mcp_client()
        status = client.get_status()

        return ToolResult.ok(
            data=status,
            summary=(
                f"{len(status['connected'])}/{len(status['registered'])} servers connected, "
                f"{status['tools']} tools available"
            ),
        )


# Convenience functions
def mcp_connect(server: str) -> ToolResult:
    """Connect to an MCP server."""
    tool = MCPConnectTool()
    return tool(server=server)


def mcp_disconnect(server: str) -> ToolResult:
    """Disconnect from an MCP server."""
    tool = MCPDisconnectTool()
    return tool(server=server)


def mcp_list_tools(server: Optional[str] = None) -> ToolResult:
    """List MCP tools."""
    tool = MCPListToolsTool()
    return tool(server=server)


def mcp_call(server: str, tool_name: str, arguments: Optional[Dict] = None) -> ToolResult:
    """Call an MCP tool."""
    tool = MCPCallTool()
    return tool(server=server, tool=tool_name, arguments=arguments or {})


def mcp_status() -> ToolResult:
    """Get MCP status."""
    tool = MCPStatusTool()
    return tool()
