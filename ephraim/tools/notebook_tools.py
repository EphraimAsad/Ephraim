"""
Notebook Tools

Provides tools for reading and editing Jupyter notebooks (.ipynb files).
"""

import json
import os
from typing import Optional, List, Dict, Any

from .base import BaseTool, ToolResult, ToolParam, ToolCategory, register_tool


def format_cell(cell: Dict, index: int) -> str:
    """Format a notebook cell for display."""
    cell_type = cell.get("cell_type", "unknown")
    source = cell.get("source", [])

    # Handle source as list or string
    if isinstance(source, list):
        content = "".join(source)
    else:
        content = source

    # Format outputs for code cells
    outputs = ""
    if cell_type == "code":
        cell_outputs = cell.get("outputs", [])
        for output in cell_outputs:
            output_type = output.get("output_type", "")

            if output_type == "stream":
                text = output.get("text", [])
                if isinstance(text, list):
                    text = "".join(text)
                outputs += f"\n[Output]\n{text}"

            elif output_type in ("execute_result", "display_data"):
                data = output.get("data", {})
                if "text/plain" in data:
                    text = data["text/plain"]
                    if isinstance(text, list):
                        text = "".join(text)
                    outputs += f"\n[Output]\n{text}"

            elif output_type == "error":
                ename = output.get("ename", "Error")
                evalue = output.get("evalue", "")
                outputs += f"\n[Error: {ename}]\n{evalue}"

    return f"[Cell {index}] ({cell_type})\n{content}{outputs}"


@register_tool
class NotebookReadTool(BaseTool):
    """
    Read a Jupyter notebook and return its cells.

    Returns formatted cell contents with outputs.
    """

    name = "notebook_read"
    description = "Read a Jupyter notebook and return cells with outputs"
    category = ToolCategory.READ_ONLY

    parameters = [
        ToolParam(
            name="path",
            type="string",
            description="Path to the .ipynb file",
            required=True,
        ),
        ToolParam(
            name="cell_range",
            type="string",
            description="Cell range to read (e.g., '0-5', '3', '10-20'). Default: all",
            required=False,
            default=None,
        ),
    ]

    def execute(self, **params) -> ToolResult:
        """Read the notebook."""
        path = params["path"]
        cell_range = params.get("cell_range")

        # Resolve path
        path = os.path.abspath(os.path.expanduser(path))

        # Validate
        if not os.path.exists(path):
            return ToolResult.fail(f"File not found: {path}")

        if not path.endswith('.ipynb'):
            return ToolResult.fail(f"Not a notebook file: {path}")

        # Read notebook
        try:
            with open(path, 'r', encoding='utf-8') as f:
                notebook = json.load(f)
        except json.JSONDecodeError as e:
            return ToolResult.fail(f"Invalid notebook JSON: {str(e)}")
        except Exception as e:
            return ToolResult.fail(f"Failed to read notebook: {str(e)}")

        cells = notebook.get("cells", [])

        # Parse cell range
        start, end = 0, len(cells)
        if cell_range:
            try:
                if '-' in cell_range:
                    start, end = map(int, cell_range.split('-'))
                    end += 1  # Make inclusive
                else:
                    start = int(cell_range)
                    end = start + 1
            except ValueError:
                pass

        # Format cells
        formatted = []
        for i, cell in enumerate(cells[start:end], start=start):
            formatted.append(format_cell(cell, i))

        content = "\n\n---\n\n".join(formatted)

        # Get metadata
        metadata = notebook.get("metadata", {})
        kernel = metadata.get("kernelspec", {}).get("display_name", "Unknown")

        return ToolResult.ok(
            data={
                "path": path,
                "total_cells": len(cells),
                "cells_shown": end - start,
                "kernel": kernel,
                "content": content,
            },
            summary=f"Read {end - start} cells from {path} (total: {len(cells)})",
        )


@register_tool
class NotebookEditTool(BaseTool):
    """
    Edit a cell in a Jupyter notebook.

    Can replace cell content, insert new cells, or delete cells.
    """

    name = "notebook_edit"
    description = "Edit, insert, or delete a cell in a Jupyter notebook"
    category = ToolCategory.EXECUTION

    parameters = [
        ToolParam(
            name="path",
            type="string",
            description="Path to the .ipynb file",
            required=True,
        ),
        ToolParam(
            name="cell_index",
            type="int",
            description="Index of the cell to edit (0-based)",
            required=True,
        ),
        ToolParam(
            name="new_source",
            type="string",
            description="New cell content (not needed for delete)",
            required=False,
            default=None,
        ),
        ToolParam(
            name="cell_type",
            type="string",
            description="Cell type: 'code' or 'markdown'",
            required=False,
            default=None,
        ),
        ToolParam(
            name="edit_mode",
            type="string",
            description="Mode: 'replace' (default), 'insert', or 'delete'",
            required=False,
            default="replace",
        ),
    ]

    def execute(self, **params) -> ToolResult:
        """Edit the notebook."""
        path = params["path"]
        cell_index = params["cell_index"]
        new_source = params.get("new_source")
        cell_type = params.get("cell_type")
        edit_mode = params.get("edit_mode", "replace")

        # Resolve path
        path = os.path.abspath(os.path.expanduser(path))

        # Validate
        if not os.path.exists(path):
            return ToolResult.fail(f"File not found: {path}")

        if not path.endswith('.ipynb'):
            return ToolResult.fail(f"Not a notebook file: {path}")

        # Read notebook
        try:
            with open(path, 'r', encoding='utf-8') as f:
                notebook = json.load(f)
        except Exception as e:
            return ToolResult.fail(f"Failed to read notebook: {str(e)}")

        cells = notebook.get("cells", [])

        # Handle different modes
        if edit_mode == "delete":
            if cell_index < 0 or cell_index >= len(cells):
                return ToolResult.fail(f"Cell index out of range: {cell_index}")

            del cells[cell_index]
            action = "Deleted"

        elif edit_mode == "insert":
            if new_source is None:
                return ToolResult.fail("new_source required for insert")

            new_cell = {
                "cell_type": cell_type or "code",
                "source": new_source.split('\n'),
                "metadata": {},
            }
            if new_cell["cell_type"] == "code":
                new_cell["outputs"] = []
                new_cell["execution_count"] = None

            # Insert after the specified index
            cells.insert(cell_index + 1, new_cell)
            action = "Inserted"

        else:  # replace
            if cell_index < 0 or cell_index >= len(cells):
                return ToolResult.fail(f"Cell index out of range: {cell_index}")

            if new_source is None:
                return ToolResult.fail("new_source required for replace")

            # Update cell
            cells[cell_index]["source"] = new_source.split('\n')
            if cell_type:
                cells[cell_index]["cell_type"] = cell_type

            # Clear outputs for code cells
            if cells[cell_index].get("cell_type") == "code":
                cells[cell_index]["outputs"] = []
                cells[cell_index]["execution_count"] = None

            action = "Replaced"

        # Write notebook back
        try:
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(notebook, f, indent=1)
        except Exception as e:
            return ToolResult.fail(f"Failed to write notebook: {str(e)}")

        return ToolResult.ok(
            data={
                "path": path,
                "cell_index": cell_index,
                "action": action.lower(),
                "total_cells": len(cells),
            },
            summary=f"{action} cell {cell_index} in {path}",
        )


# Convenience functions
def notebook_read(path: str, cell_range: Optional[str] = None) -> ToolResult:
    """Read a notebook."""
    tool = NotebookReadTool()
    return tool(path=path, cell_range=cell_range)


def notebook_edit(
    path: str,
    cell_index: int,
    new_source: Optional[str] = None,
    edit_mode: str = "replace",
) -> ToolResult:
    """Edit a notebook cell."""
    tool = NotebookEditTool()
    return tool(
        path=path,
        cell_index=cell_index,
        new_source=new_source,
        edit_mode=edit_mode,
    )
