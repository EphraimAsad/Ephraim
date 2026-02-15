"""
MCP Protocol Helpers

JSON-RPC 2.0 protocol implementation for MCP communication.
"""

import json
import uuid
from dataclasses import dataclass, field
from typing import Dict, Any, Optional, Union


@dataclass
class JSONRPCRequest:
    """JSON-RPC 2.0 request object."""
    method: str
    params: Dict[str, Any] = field(default_factory=dict)
    id: str = field(default_factory=lambda: uuid.uuid4().hex)
    jsonrpc: str = "2.0"

    def to_json(self) -> str:
        """Serialize to JSON string."""
        return json.dumps({
            "jsonrpc": self.jsonrpc,
            "id": self.id,
            "method": self.method,
            "params": self.params,
        })

    def to_bytes(self) -> bytes:
        """Serialize to bytes with newline."""
        return self.to_json().encode("utf-8") + b"\n"


@dataclass
class JSONRPCError:
    """JSON-RPC 2.0 error object."""
    code: int
    message: str
    data: Optional[Any] = None

    @classmethod
    def from_dict(cls, d: Dict) -> "JSONRPCError":
        return cls(
            code=d.get("code", -1),
            message=d.get("message", "Unknown error"),
            data=d.get("data"),
        )


@dataclass
class JSONRPCResponse:
    """JSON-RPC 2.0 response object."""
    id: str
    result: Optional[Any] = None
    error: Optional[JSONRPCError] = None
    jsonrpc: str = "2.0"

    @property
    def success(self) -> bool:
        """Check if response is successful."""
        return self.error is None

    @classmethod
    def from_json(cls, json_str: str) -> "JSONRPCResponse":
        """Parse from JSON string."""
        data = json.loads(json_str)
        return cls.from_dict(data)

    @classmethod
    def from_dict(cls, d: Dict) -> "JSONRPCResponse":
        """Parse from dictionary."""
        error = None
        if "error" in d and d["error"]:
            error = JSONRPCError.from_dict(d["error"])

        return cls(
            id=d.get("id", ""),
            result=d.get("result"),
            error=error,
            jsonrpc=d.get("jsonrpc", "2.0"),
        )


# Standard JSON-RPC error codes
class ErrorCodes:
    """Standard JSON-RPC 2.0 error codes."""
    PARSE_ERROR = -32700
    INVALID_REQUEST = -32600
    METHOD_NOT_FOUND = -32601
    INVALID_PARAMS = -32602
    INTERNAL_ERROR = -32603


def create_request(method: str, params: Optional[Dict] = None) -> JSONRPCRequest:
    """Create a JSON-RPC request."""
    return JSONRPCRequest(
        method=method,
        params=params or {},
    )


def parse_response(json_str: str) -> JSONRPCResponse:
    """Parse a JSON-RPC response."""
    return JSONRPCResponse.from_json(json_str)
