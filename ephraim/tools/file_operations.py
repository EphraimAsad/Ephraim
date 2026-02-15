"""
File Operations Tools

Provides delete, move, and copy operations for files.

Safety features:
- Blocks dangerous system paths
- Prevents accidental deletion of critical files
- Creates backups before destructive operations
"""

import os
import shutil
from datetime import datetime
from typing import Optional

from .base import BaseTool, ToolResult, ToolParam, ToolCategory, register_tool
from .write_file import is_dangerous_path


# Additional patterns that should not be deleted
PROTECTED_PATTERNS = [
    '.git',  # Git repository data
    '.env',  # Environment files (may contain secrets)
    'node_modules',  # Large dependency folders (delete via rm command if needed)
]


def is_protected_file(path: str) -> bool:
    """Check if a file/directory is protected from deletion."""
    basename = os.path.basename(path).lower()
    return basename in [p.lower() for p in PROTECTED_PATTERNS]


@register_tool
class DeleteFileTool(BaseTool):
    """
    Delete a file.

    Safety features:
    - Blocks deletion of system paths
    - Blocks deletion of .git, .env, etc.
    - Creates backup before deletion (optional)
    """

    name = "delete_file"
    description = "Delete a file from the filesystem"
    category = ToolCategory.EXECUTION  # Requires approval

    parameters = [
        ToolParam(
            name="path",
            type="string",
            description="Path to the file to delete",
            required=True,
        ),
        ToolParam(
            name="backup",
            type="bool",
            description="Create backup before deleting",
            required=False,
            default=True,
        ),
    ]

    def execute(self, **params) -> ToolResult:
        """Delete the file."""
        path = params["path"]
        backup = params.get("backup", True)

        # Resolve path
        path = os.path.abspath(os.path.expanduser(path))

        # Safety checks
        if is_dangerous_path(path):
            return ToolResult.fail(f"Cannot delete protected system path: {path}")

        if is_protected_file(path):
            return ToolResult.fail(
                f"Cannot delete protected file/directory: {os.path.basename(path)}. "
                f"Use run_command if you really need to delete this."
            )

        # Check file exists
        if not os.path.exists(path):
            return ToolResult.fail(f"File not found: {path}")

        # Check it's a file (not directory)
        if os.path.isdir(path):
            return ToolResult.fail(
                f"Path is a directory, not a file: {path}. "
                f"Use delete_directory for directories."
            )

        # Create backup
        backup_path = None
        if backup:
            backup_path = self._create_backup(path)

        # Delete the file
        try:
            os.remove(path)
        except Exception as e:
            return ToolResult.fail(f"Failed to delete file: {str(e)}")

        return ToolResult.ok(
            data={
                "path": path,
                "backup_path": backup_path,
            },
            summary=f"Deleted {path}" + (f" (backup at {backup_path})" if backup_path else ""),
        )

    def _create_backup(self, path: str) -> Optional[str]:
        """Create a backup before deletion."""
        try:
            backup_dir = os.path.join(os.path.dirname(path), '.ephraim_backups')
            os.makedirs(backup_dir, exist_ok=True)

            filename = os.path.basename(path)
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_filename = f"{filename}.{timestamp}.deleted.bak"
            backup_path = os.path.join(backup_dir, backup_filename)

            shutil.copy2(path, backup_path)
            return backup_path
        except Exception:
            return None


@register_tool
class MoveFileTool(BaseTool):
    """
    Move or rename a file.

    Can move files between directories or rename within same directory.
    """

    name = "move_file"
    description = "Move or rename a file"
    category = ToolCategory.EXECUTION  # Requires approval

    parameters = [
        ToolParam(
            name="source",
            type="string",
            description="Source file path",
            required=True,
        ),
        ToolParam(
            name="destination",
            type="string",
            description="Destination file path",
            required=True,
        ),
        ToolParam(
            name="overwrite",
            type="bool",
            description="Overwrite destination if it exists",
            required=False,
            default=False,
        ),
    ]

    def execute(self, **params) -> ToolResult:
        """Move the file."""
        source = os.path.abspath(os.path.expanduser(params["source"]))
        destination = os.path.abspath(os.path.expanduser(params["destination"]))
        overwrite = params.get("overwrite", False)

        # Safety checks
        if is_dangerous_path(source):
            return ToolResult.fail(f"Cannot move from protected path: {source}")
        if is_dangerous_path(destination):
            return ToolResult.fail(f"Cannot move to protected path: {destination}")

        # Check source exists
        if not os.path.exists(source):
            return ToolResult.fail(f"Source file not found: {source}")

        if os.path.isdir(source):
            return ToolResult.fail(f"Source is a directory: {source}. Use for files only.")

        # Check destination
        if os.path.exists(destination):
            if os.path.isdir(destination):
                # Move into directory
                destination = os.path.join(destination, os.path.basename(source))
            elif not overwrite:
                return ToolResult.fail(
                    f"Destination exists: {destination}. Set overwrite=true to replace."
                )

        # Create destination directory if needed
        dest_dir = os.path.dirname(destination)
        if dest_dir and not os.path.exists(dest_dir):
            try:
                os.makedirs(dest_dir, exist_ok=True)
            except Exception as e:
                return ToolResult.fail(f"Failed to create destination directory: {str(e)}")

        # Move the file
        try:
            shutil.move(source, destination)
        except Exception as e:
            return ToolResult.fail(f"Failed to move file: {str(e)}")

        return ToolResult.ok(
            data={
                "source": source,
                "destination": destination,
            },
            summary=f"Moved {source} to {destination}",
        )


@register_tool
class CopyFileTool(BaseTool):
    """
    Copy a file to a new location.

    Preserves file metadata (timestamps, permissions).
    """

    name = "copy_file"
    description = "Copy a file to a new location"
    category = ToolCategory.EXECUTION  # Requires approval

    parameters = [
        ToolParam(
            name="source",
            type="string",
            description="Source file path",
            required=True,
        ),
        ToolParam(
            name="destination",
            type="string",
            description="Destination file path",
            required=True,
        ),
        ToolParam(
            name="overwrite",
            type="bool",
            description="Overwrite destination if it exists",
            required=False,
            default=False,
        ),
    ]

    def execute(self, **params) -> ToolResult:
        """Copy the file."""
        source = os.path.abspath(os.path.expanduser(params["source"]))
        destination = os.path.abspath(os.path.expanduser(params["destination"]))
        overwrite = params.get("overwrite", False)

        # Safety checks
        if is_dangerous_path(destination):
            return ToolResult.fail(f"Cannot copy to protected path: {destination}")

        # Check source exists
        if not os.path.exists(source):
            return ToolResult.fail(f"Source file not found: {source}")

        if os.path.isdir(source):
            return ToolResult.fail(f"Source is a directory: {source}. Use for files only.")

        # Check destination
        if os.path.exists(destination):
            if os.path.isdir(destination):
                # Copy into directory
                destination = os.path.join(destination, os.path.basename(source))
            elif not overwrite:
                return ToolResult.fail(
                    f"Destination exists: {destination}. Set overwrite=true to replace."
                )

        # Create destination directory if needed
        dest_dir = os.path.dirname(destination)
        if dest_dir and not os.path.exists(dest_dir):
            try:
                os.makedirs(dest_dir, exist_ok=True)
            except Exception as e:
                return ToolResult.fail(f"Failed to create destination directory: {str(e)}")

        # Copy the file (preserving metadata)
        try:
            shutil.copy2(source, destination)
        except Exception as e:
            return ToolResult.fail(f"Failed to copy file: {str(e)}")

        # Get file size
        size = os.path.getsize(destination)

        return ToolResult.ok(
            data={
                "source": source,
                "destination": destination,
                "size": size,
            },
            summary=f"Copied {source} to {destination} ({size} bytes)",
        )


# Convenience functions
def delete_file(path: str, backup: bool = True) -> ToolResult:
    """Delete a file."""
    tool = DeleteFileTool()
    return tool(path=path, backup=backup)


def move_file(source: str, destination: str, overwrite: bool = False) -> ToolResult:
    """Move a file."""
    tool = MoveFileTool()
    return tool(source=source, destination=destination, overwrite=overwrite)


def copy_file(source: str, destination: str, overwrite: bool = False) -> ToolResult:
    """Copy a file."""
    tool = CopyFileTool()
    return tool(source=source, destination=destination, overwrite=overwrite)
