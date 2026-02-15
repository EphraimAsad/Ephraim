"""
MCP Client

Client for connecting to and communicating with MCP servers.
Handles server lifecycle, tool discovery, and tool invocation.
"""

import json
import os
import subprocess
import sys
import threading
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional
from pathlib import Path

from .protocol import JSONRPCRequest, JSONRPCResponse, create_request, parse_response


@dataclass
class MCPTool:
    """Represents a tool provided by an MCP server."""
    name: str
    description: str
    input_schema: Dict[str, Any] = field(default_factory=dict)
    server: str = ""  # Server that provides this tool

    @classmethod
    def from_dict(cls, d: Dict, server: str = "") -> "MCPTool":
        return cls(
            name=d.get("name", ""),
            description=d.get("description", ""),
            input_schema=d.get("inputSchema", d.get("input_schema", {})),
            server=server,
        )


@dataclass
class MCPServer:
    """Configuration for an MCP server."""
    name: str
    command: str
    args: List[str] = field(default_factory=list)
    env: Dict[str, str] = field(default_factory=dict)
    cwd: Optional[str] = None

    @classmethod
    def from_config(cls, name: str, config_str: str) -> "MCPServer":
        """
        Parse server config from string.

        Format: command arg1 arg2 ...
        Example: uvx mcp-server-sqlite --db-path ./data.db
        """
        parts = config_str.strip().split()
        if not parts:
            raise ValueError(f"Invalid server config: {config_str}")

        return cls(
            name=name,
            command=parts[0],
            args=parts[1:] if len(parts) > 1 else [],
        )


class MCPConnection:
    """Manages a connection to a single MCP server."""

    def __init__(self, server: MCPServer):
        self.server = server
        self.process: Optional[subprocess.Popen] = None
        self.tools: List[MCPTool] = []
        self._lock = threading.Lock()
        self._request_id = 0

    @property
    def connected(self) -> bool:
        """Check if server is connected."""
        return self.process is not None and self.process.poll() is None

    def connect(self) -> bool:
        """Start and connect to the MCP server."""
        if self.connected:
            return True

        try:
            # Build environment
            env = os.environ.copy()
            env.update(self.server.env)

            # Determine shell based on platform
            if sys.platform == "win32":
                # On Windows, use cmd to find commands in PATH
                shell_cmd = f"{self.server.command} {' '.join(self.server.args)}"
                self.process = subprocess.Popen(
                    shell_cmd,
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    env=env,
                    cwd=self.server.cwd,
                    shell=True,
                )
            else:
                # On Unix, run directly
                self.process = subprocess.Popen(
                    [self.server.command] + self.server.args,
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    env=env,
                    cwd=self.server.cwd,
                )

            # Initialize connection
            self._initialize()
            return True

        except Exception as e:
            self.process = None
            raise ConnectionError(f"Failed to start MCP server '{self.server.name}': {e}")

    def _initialize(self) -> None:
        """Initialize the MCP connection and discover tools."""
        # Send initialize request
        response = self._send_request("initialize", {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {
                "name": "ephraim",
                "version": "0.2.0",
            },
        })

        if not response.success:
            raise ConnectionError(f"Initialize failed: {response.error}")

        # Send initialized notification
        self._send_notification("notifications/initialized", {})

        # Discover tools
        self._discover_tools()

    def _discover_tools(self) -> None:
        """Discover available tools from the server."""
        response = self._send_request("tools/list", {})

        if response.success and response.result:
            tools_data = response.result.get("tools", [])
            self.tools = [
                MCPTool.from_dict(t, self.server.name)
                for t in tools_data
            ]

    def _send_request(self, method: str, params: Dict) -> JSONRPCResponse:
        """Send a JSON-RPC request and wait for response."""
        with self._lock:
            if not self.process or not self.process.stdin or not self.process.stdout:
                return JSONRPCResponse(
                    id="",
                    error={"code": -1, "message": "Not connected"},
                )

            # Create and send request
            request = create_request(method, params)
            try:
                self.process.stdin.write(request.to_bytes())
                self.process.stdin.flush()

                # Read response
                response_line = self.process.stdout.readline()
                if not response_line:
                    return JSONRPCResponse(
                        id=request.id,
                        error={"code": -1, "message": "No response from server"},
                    )

                return parse_response(response_line.decode("utf-8"))

            except Exception as e:
                return JSONRPCResponse(
                    id=request.id,
                    error={"code": -1, "message": str(e)},
                )

    def _send_notification(self, method: str, params: Dict) -> None:
        """Send a JSON-RPC notification (no response expected)."""
        with self._lock:
            if not self.process or not self.process.stdin:
                return

            # Notifications have no id
            notification = {
                "jsonrpc": "2.0",
                "method": method,
                "params": params,
            }

            try:
                self.process.stdin.write(json.dumps(notification).encode() + b"\n")
                self.process.stdin.flush()
            except Exception:
                pass

    def call_tool(self, tool_name: str, arguments: Dict) -> Any:
        """Call a tool on this server."""
        response = self._send_request("tools/call", {
            "name": tool_name,
            "arguments": arguments,
        })

        if response.success:
            return response.result
        else:
            raise Exception(f"Tool call failed: {response.error}")

    def disconnect(self) -> None:
        """Disconnect from the server."""
        if self.process:
            try:
                self.process.terminate()
                self.process.wait(timeout=5)
            except Exception:
                self.process.kill()
            finally:
                self.process = None
                self.tools = []


class MCPClient:
    """
    Client for managing multiple MCP server connections.

    Singleton pattern - use get_mcp_client() to access.
    """

    _instance: Optional["MCPClient"] = None

    def __init__(self):
        self.servers: Dict[str, MCPServer] = {}
        self.connections: Dict[str, MCPConnection] = {}

    @classmethod
    def get_instance(cls) -> "MCPClient":
        """Get the singleton instance."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def register_server(self, server: MCPServer) -> None:
        """Register an MCP server configuration."""
        self.servers[server.name] = server

    def load_config(self, config_path: Optional[str] = None) -> int:
        """
        Load MCP server configurations from file.

        Supports:
        - Ephraim.md (section: # MCP Servers)
        - mcp.json

        Returns number of servers loaded.
        """
        count = 0

        # Try Ephraim.md
        if config_path and os.path.exists(config_path):
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                count += self._parse_ephraim_md_servers(content)
            except Exception:
                pass

        # Try mcp.json in current directory
        mcp_json = Path("mcp.json")
        if mcp_json.exists():
            try:
                with open(mcp_json, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                count += self._parse_mcp_json(data)
            except Exception:
                pass

        return count

    def _parse_ephraim_md_servers(self, content: str) -> int:
        """Parse MCP servers from Ephraim.md content."""
        count = 0
        in_mcp_section = False

        for line in content.split('\n'):
            line = line.strip()

            if line.lower().startswith('# mcp servers'):
                in_mcp_section = True
                continue

            if line.startswith('# ') and in_mcp_section:
                in_mcp_section = False
                continue

            if in_mcp_section and line.startswith('- '):
                try:
                    # Format: - name: command args...
                    if ':' in line[2:]:
                        name, config = line[2:].split(':', 1)
                        server = MCPServer.from_config(name.strip(), config.strip())
                        self.register_server(server)
                        count += 1
                except Exception:
                    pass

        return count

    def _parse_mcp_json(self, data: Dict) -> int:
        """Parse MCP servers from mcp.json format."""
        count = 0
        servers = data.get("mcpServers", data.get("servers", {}))

        for name, config in servers.items():
            try:
                server = MCPServer(
                    name=name,
                    command=config.get("command", ""),
                    args=config.get("args", []),
                    env=config.get("env", {}),
                )
                self.register_server(server)
                count += 1
            except Exception:
                pass

        return count

    def connect(self, server_name: str) -> bool:
        """Connect to a registered MCP server."""
        if server_name not in self.servers:
            raise ValueError(f"Unknown server: {server_name}")

        if server_name in self.connections and self.connections[server_name].connected:
            return True

        server = self.servers[server_name]
        connection = MCPConnection(server)

        try:
            connection.connect()
            self.connections[server_name] = connection
            return True
        except Exception:
            return False

    def disconnect(self, server_name: str) -> None:
        """Disconnect from a server."""
        if server_name in self.connections:
            self.connections[server_name].disconnect()
            del self.connections[server_name]

    def disconnect_all(self) -> None:
        """Disconnect from all servers."""
        for name in list(self.connections.keys()):
            self.disconnect(name)

    def list_tools(self, server_name: Optional[str] = None) -> List[MCPTool]:
        """
        List available tools.

        If server_name is provided, list tools from that server only.
        Otherwise, list tools from all connected servers.
        """
        if server_name:
            if server_name not in self.connections:
                return []
            return self.connections[server_name].tools

        # All tools from all servers
        all_tools = []
        for conn in self.connections.values():
            all_tools.extend(conn.tools)
        return all_tools

    def call_tool(self, server_name: str, tool_name: str, arguments: Dict) -> Any:
        """Call a tool on a specific server."""
        if server_name not in self.connections:
            raise ValueError(f"Not connected to server: {server_name}")

        return self.connections[server_name].call_tool(tool_name, arguments)

    def get_tool(self, tool_name: str) -> Optional[MCPTool]:
        """Find a tool by name across all connected servers."""
        for conn in self.connections.values():
            for tool in conn.tools:
                if tool.name == tool_name:
                    return tool
        return None

    def get_status(self) -> Dict[str, Any]:
        """Get status of all servers."""
        return {
            "registered": list(self.servers.keys()),
            "connected": [
                name for name, conn in self.connections.items()
                if conn.connected
            ],
            "tools": len(self.list_tools()),
        }


# Singleton accessor
def get_mcp_client() -> MCPClient:
    """Get the MCP client singleton."""
    return MCPClient.get_instance()
