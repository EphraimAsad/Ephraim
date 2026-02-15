"""
Directory Tools

Provides create and delete operations for directories.

Safety features:
- Blocks dangerous system paths
- Requires explicit recursive flag for non-empty directories
- Additional confirmation for large directory deletions
"""

import os
import shutil
from typing import Optional

from .base import BaseTool, ToolResult, ToolParam, ToolCategory, register_tool
from .write_file import is_dangerous_path


# Directories that should never be deleted even with recursive flag
ABSOLUTELY_PROTECTED = [
    '.git',  # Repository data
    'node_modules',  # Dependencies (use npm/yarn commands)
    '__pycache__',  # Python cache (auto-regenerated)
    '.venv', 'venv',  # Virtual environments
    '.env',  # Environment directories
]


def is_absolutely_protected(path: str) -> bool:
    """Check if directory is absolutely protected from deletion."""
    basename = os.path.basename(path).lower()
    return basename in [p.lower() for p in ABSOLUTELY_PROTECTED]


@register_tool
class CreateDirectoryTool(BaseTool):
    """
    Create a new directory.

    Can create nested directories (like mkdir -p).
    """

    name = "create_directory"
    description = "Create a new directory (and parent directories if needed)"
    category = ToolCategory.EXECUTION  # Requires approval

    parameters = [
        ToolParam(
            name="path",
            type="string",
            description="Path to the directory to create",
            required=True,
        ),
        ToolParam(
            name="parents",
            type="bool",
            description="Create parent directories if they don't exist (like mkdir -p)",
            required=False,
            default=True,
        ),
    ]

    def execute(self, **params) -> ToolResult:
        """Create the directory."""
        path = params["path"]
        parents = params.get("parents", True)

        # Resolve path
        path = os.path.abspath(os.path.expanduser(path))

        # Safety check
        if is_dangerous_path(path):
            return ToolResult.fail(f"Cannot create directory in protected path: {path}")

        # Check if already exists
        if os.path.exists(path):
            if os.path.isdir(path):
                return ToolResult.ok(
                    data={"path": path, "already_exists": True},
                    summary=f"Directory already exists: {path}",
                )
            else:
                return ToolResult.fail(f"Path exists but is not a directory: {path}")

        # Create directory
        try:
            if parents:
                os.makedirs(path, exist_ok=True)
            else:
                os.mkdir(path)
        except FileNotFoundError:
            return ToolResult.fail(
                f"Parent directory does not exist. Set parents=true to create it."
            )
        except Exception as e:
            return ToolResult.fail(f"Failed to create directory: {str(e)}")

        return ToolResult.ok(
            data={"path": path, "created": True},
            summary=f"Created directory: {path}",
        )


@register_tool
class DeleteDirectoryTool(BaseTool):
    """
    Delete a directory.

    By default only deletes empty directories.
    Set recursive=true to delete non-empty directories.
    """

    name = "delete_directory"
    description = "Delete a directory (empty by default, or recursive)"
    category = ToolCategory.EXECUTION  # Requires approval

    parameters = [
        ToolParam(
            name="path",
            type="string",
            description="Path to the directory to delete",
            required=True,
        ),
        ToolParam(
            name="recursive",
            type="bool",
            description="Delete directory and all contents recursively",
            required=False,
            default=False,
        ),
    ]

    def execute(self, **params) -> ToolResult:
        """Delete the directory."""
        path = params["path"]
        recursive = params.get("recursive", False)

        # Resolve path
        path = os.path.abspath(os.path.expanduser(path))

        # Safety checks
        if is_dangerous_path(path):
            return ToolResult.fail(f"Cannot delete protected system path: {path}")

        if is_absolutely_protected(path):
            return ToolResult.fail(
                f"Cannot delete protected directory: {os.path.basename(path)}. "
                f"Use run_command with caution if you really need to delete this."
            )

        # Check exists
        if not os.path.exists(path):
            return ToolResult.fail(f"Directory not found: {path}")

        # Check it's a directory
        if not os.path.isdir(path):
            return ToolResult.fail(f"Path is not a directory: {path}")

        # Count contents for reporting
        try:
            contents = os.listdir(path)
            file_count = len(contents)
        except Exception:
            file_count = 0

        # Check if empty
        if file_count > 0 and not recursive:
            return ToolResult.fail(
                f"Directory not empty ({file_count} items). "
                f"Set recursive=true to delete contents."
            )

        # Additional safety for large directories
        if recursive and file_count > 100:
            total_files = sum(
                len(files) for _, _, files in os.walk(path)
            )
            if total_files > 1000:
                return ToolResult.fail(
                    f"Directory contains {total_files} files. "
                    f"Use run_command for large directory deletions."
                )

        # Delete
        try:
            if recursive:
                shutil.rmtree(path)
            else:
                os.rmdir(path)
        except Exception as e:
            return ToolResult.fail(f"Failed to delete directory: {str(e)}")

        return ToolResult.ok(
            data={
                "path": path,
                "recursive": recursive,
                "items_deleted": file_count if recursive else 0,
            },
            summary=f"Deleted directory: {path}" + (f" ({file_count} items)" if recursive and file_count else ""),
        )


# Convenience functions
def create_directory(path: str, parents: bool = True) -> ToolResult:
    """Create a directory."""
    tool = CreateDirectoryTool()
    return tool(path=path, parents=parents)


def delete_directory(path: str, recursive: bool = False) -> ToolResult:
    """Delete a directory."""
    tool = DeleteDirectoryTool()
    return tool(path=path, recursive=recursive)
