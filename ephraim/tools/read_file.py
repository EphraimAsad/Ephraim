"""
Read File Tool

Reads file contents with line numbers and handles various edge cases.
"""

import os
from typing import List

from .base import BaseTool, ToolResult, ToolParam, ToolCategory, register_tool


@register_tool
class ReadFileTool(BaseTool):
    """
    Read the contents of a file.

    Returns file contents with line numbers.
    Handles encoding errors gracefully.
    Truncates large files with notice.
    """

    name = "read_file"
    description = "Read the contents of a file with line numbers"
    category = ToolCategory.READ_ONLY

    parameters = [
        ToolParam(
            name="path",
            type="string",
            description="Path to the file to read",
            required=True,
        ),
        ToolParam(
            name="start_line",
            type="int",
            description="Starting line number (1-indexed)",
            required=False,
            default=1,
        ),
        ToolParam(
            name="max_lines",
            type="int",
            description="Maximum number of lines to read",
            required=False,
            default=500,
        ),
    ]

    # Maximum file size to read (5MB)
    MAX_FILE_SIZE = 5 * 1024 * 1024

    def execute(self, **params) -> ToolResult:
        """Read the file and return contents with line numbers."""
        path = params["path"]
        start_line = params.get("start_line", 1)
        max_lines = params.get("max_lines", 500)

        # Resolve path
        path = os.path.abspath(os.path.expanduser(path))

        # Check if file exists
        if not os.path.exists(path):
            return ToolResult.fail(f"File not found: {path}")

        # Check if it's a file
        if not os.path.isfile(path):
            return ToolResult.fail(f"Not a file: {path}")

        # Check file size
        file_size = os.path.getsize(path)
        if file_size > self.MAX_FILE_SIZE:
            return ToolResult.fail(
                f"File too large ({file_size / 1024 / 1024:.1f}MB). "
                f"Maximum size: {self.MAX_FILE_SIZE / 1024 / 1024:.1f}MB"
            )

        # Try to read the file with different encodings
        content = None
        encoding_used = None

        for encoding in ['utf-8', 'latin-1', 'cp1252']:
            try:
                with open(path, 'r', encoding=encoding) as f:
                    content = f.read()
                    encoding_used = encoding
                    break
            except UnicodeDecodeError:
                continue
            except Exception as e:
                return ToolResult.fail(f"Error reading file: {str(e)}")

        if content is None:
            return ToolResult.fail("Could not decode file with any supported encoding")

        # Split into lines
        lines = content.split('\n')
        total_lines = len(lines)

        # Apply line range
        start_idx = max(0, start_line - 1)
        end_idx = min(start_idx + max_lines, total_lines)
        selected_lines = lines[start_idx:end_idx]

        # Format with line numbers
        numbered_lines: List[str] = []
        for i, line in enumerate(selected_lines, start=start_line):
            numbered_lines.append(f"{i:6d} | {line}")

        output = '\n'.join(numbered_lines)
        truncated = end_idx < total_lines

        return ToolResult.ok(
            data={
                "path": path,
                "content": output,
                "total_lines": total_lines,
                "start_line": start_line,
                "end_line": start_idx + len(selected_lines),
                "lines_returned": len(selected_lines),
                "truncated": truncated,
                "encoding": encoding_used,
                "file_size": file_size,
            },
            summary=f"Read {len(selected_lines)} lines from {path}"
            + (f" (truncated, {total_lines} total)" if truncated else ""),
        )
