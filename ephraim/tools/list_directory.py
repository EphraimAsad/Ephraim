"""
List Directory Tool

Lists directory contents with file types and sizes.
"""

import os
import subprocess
from typing import List, Dict, Any, Set

from .base import BaseTool, ToolResult, ToolParam, ToolCategory, register_tool


def get_gitignore_patterns(directory: str) -> Set[str]:
    """
    Get gitignore patterns for the directory.

    Uses git check-ignore to properly handle all gitignore rules.
    """
    ignored: Set[str] = set()

    try:
        # Get list of all files
        for root, dirs, files in os.walk(directory):
            for name in files + dirs:
                full_path = os.path.join(root, name)
                rel_path = os.path.relpath(full_path, directory)

                # Check if ignored by git
                result = subprocess.run(
                    ['git', 'check-ignore', '-q', rel_path],
                    cwd=directory,
                    capture_output=True,
                    timeout=5,
                )
                if result.returncode == 0:
                    ignored.add(rel_path)
    except Exception:
        pass

    return ignored


@register_tool
class ListDirectoryTool(BaseTool):
    """
    List the contents of a directory.

    Shows file types, sizes, and can optionally respect .gitignore.
    """

    name = "list_directory"
    description = "List the contents of a directory with file information"
    category = ToolCategory.READ_ONLY

    parameters = [
        ToolParam(
            name="path",
            type="string",
            description="Path to the directory to list",
            required=True,
        ),
        ToolParam(
            name="recursive",
            type="bool",
            description="Whether to list recursively",
            required=False,
            default=False,
        ),
        ToolParam(
            name="max_depth",
            type="int",
            description="Maximum recursion depth (if recursive)",
            required=False,
            default=3,
        ),
        ToolParam(
            name="respect_gitignore",
            type="bool",
            description="Whether to skip files in .gitignore",
            required=False,
            default=True,
        ),
        ToolParam(
            name="show_hidden",
            type="bool",
            description="Whether to show hidden files (starting with .)",
            required=False,
            default=False,
        ),
    ]

    def execute(self, **params) -> ToolResult:
        """List directory contents."""
        path = params["path"]
        recursive = params.get("recursive", False)
        max_depth = params.get("max_depth", 3)
        respect_gitignore = params.get("respect_gitignore", True)
        show_hidden = params.get("show_hidden", False)

        # Resolve path
        path = os.path.abspath(os.path.expanduser(path))

        # Check if directory exists
        if not os.path.exists(path):
            return ToolResult.fail(f"Directory not found: {path}")

        # Check if it's a directory
        if not os.path.isdir(path):
            return ToolResult.fail(f"Not a directory: {path}")

        # Get gitignore patterns if needed
        ignored: Set[str] = set()
        if respect_gitignore:
            ignored = get_gitignore_patterns(path)

        # List entries
        entries: List[Dict[str, Any]] = []

        def list_dir(dir_path: str, current_depth: int = 0) -> None:
            if recursive and current_depth >= max_depth:
                return

            try:
                items = sorted(os.listdir(dir_path))
            except PermissionError:
                return

            for item in items:
                # Skip hidden files unless requested
                if not show_hidden and item.startswith('.'):
                    continue

                full_path = os.path.join(dir_path, item)
                rel_path = os.path.relpath(full_path, path)

                # Skip gitignored files
                if respect_gitignore and rel_path in ignored:
                    continue

                # Get file info
                try:
                    stat = os.stat(full_path)
                    is_dir = os.path.isdir(full_path)

                    entry = {
                        "name": item,
                        "path": rel_path,
                        "type": "directory" if is_dir else "file",
                        "size": stat.st_size if not is_dir else None,
                        "depth": current_depth,
                    }

                    # Get file extension for files
                    if not is_dir:
                        _, ext = os.path.splitext(item)
                        entry["extension"] = ext.lower() if ext else None

                    entries.append(entry)

                    # Recurse into directories
                    if recursive and is_dir:
                        list_dir(full_path, current_depth + 1)

                except (PermissionError, OSError):
                    continue

        list_dir(path)

        # Format output
        output_lines = []
        for entry in entries:
            indent = "  " * entry["depth"]
            if entry["type"] == "directory":
                output_lines.append(f"{indent}{entry['name']}/")
            else:
                size = entry.get("size", 0)
                size_str = self._format_size(size)
                output_lines.append(f"{indent}{entry['name']} ({size_str})")

        # Count statistics
        file_count = sum(1 for e in entries if e["type"] == "file")
        dir_count = sum(1 for e in entries if e["type"] == "directory")

        return ToolResult.ok(
            data={
                "path": path,
                "entries": entries,
                "file_count": file_count,
                "directory_count": dir_count,
                "total_count": len(entries),
                "recursive": recursive,
                "output": "\n".join(output_lines),
            },
            summary=f"Listed {path}: {file_count} files, {dir_count} directories",
        )

    @staticmethod
    def _format_size(size: int) -> str:
        """Format file size in human-readable form."""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024:
                return f"{size:.1f}{unit}" if unit != 'B' else f"{size}{unit}"
            size /= 1024
        return f"{size:.1f}TB"
