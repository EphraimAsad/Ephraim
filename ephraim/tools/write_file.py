"""
Write File Tool

Creates new files or overwrites existing files with content.
This is the primary tool for file creation in Ephraim.

Safety features:
- Blocks dangerous system paths
- Creates parent directories if needed
- Creates backup before overwriting existing files
"""

import os
import shutil
from datetime import datetime
from typing import Optional, List

from .base import BaseTool, ToolResult, ToolParam, ToolCategory, register_tool


# Dangerous paths that should never be written to
DANGEROUS_PATHS = [
    # Unix/Linux
    '/', '/bin', '/boot', '/dev', '/etc', '/lib', '/lib64',
    '/proc', '/root', '/sbin', '/sys', '/usr', '/var',
    # Windows
    'c:\\', 'c:\\windows', 'c:\\program files', 'c:\\program files (x86)',
    'c:\\programdata', 'c:\\users\\public',
    # macOS
    '/system', '/library', '/applications',
]

# File extensions that are typically dangerous to create
DANGEROUS_EXTENSIONS = [
    '.exe', '.dll', '.sys', '.bat', '.cmd', '.com', '.scr',
    '.vbs', '.vbe', '.js', '.jse', '.ws', '.wsf', '.wsc',
    '.msc', '.msi', '.msp', '.pif', '.hta', '.cpl',
]


def is_dangerous_path(path: str) -> bool:
    """Check if a path is dangerous to write to."""
    path_lower = os.path.abspath(path).lower()

    # Check exact matches and prefixes
    for dangerous in DANGEROUS_PATHS:
        dangerous_lower = dangerous.lower()
        if path_lower == dangerous_lower:
            return True
        # Check if trying to write directly in a dangerous directory
        if path_lower.startswith(dangerous_lower + os.sep):
            # Allow subdirectories of user home
            home = os.path.expanduser('~').lower()
            if path_lower.startswith(home):
                return False
            # Block system directories
            if dangerous_lower in ['/usr', '/var', 'c:\\windows', 'c:\\program files']:
                return True

    return False


def has_dangerous_extension(path: str) -> bool:
    """Check if file has a dangerous extension."""
    _, ext = os.path.splitext(path.lower())
    return ext in DANGEROUS_EXTENSIONS


@register_tool
class WriteFileTool(BaseTool):
    """
    Write content to a file (create or overwrite).

    This is the primary tool for creating new files.
    Creates parent directories automatically if needed.
    Creates backup before overwriting existing files.
    """

    name = "write_file"
    description = "Create a new file or overwrite an existing file with content"
    category = ToolCategory.EXECUTION  # Requires approval

    parameters = [
        ToolParam(
            name="path",
            type="string",
            description="Path to the file to write",
            required=True,
        ),
        ToolParam(
            name="content",
            type="string",
            description="Content to write to the file",
            required=True,
        ),
        ToolParam(
            name="create_dirs",
            type="bool",
            description="Create parent directories if they don't exist",
            required=False,
            default=True,
        ),
        ToolParam(
            name="backup",
            type="bool",
            description="Create backup if file exists before overwriting",
            required=False,
            default=True,
        ),
    ]

    def execute(self, **params) -> ToolResult:
        """Write content to the file."""
        path = params["path"]
        content = params["content"]
        create_dirs = params.get("create_dirs", True)
        backup = params.get("backup", True)

        # Resolve path
        path = os.path.abspath(os.path.expanduser(path))

        # Safety checks
        validation_error = self._validate_write(path)
        if validation_error:
            return ToolResult.fail(validation_error)

        # Check if file exists (for backup and messaging)
        file_exists = os.path.exists(path)
        is_overwrite = file_exists and os.path.isfile(path)

        # Create parent directories if needed
        parent_dir = os.path.dirname(path)
        if parent_dir and not os.path.exists(parent_dir):
            if create_dirs:
                try:
                    os.makedirs(parent_dir, exist_ok=True)
                except Exception as e:
                    return ToolResult.fail(f"Failed to create directories: {str(e)}")
            else:
                return ToolResult.fail(f"Parent directory does not exist: {parent_dir}")

        # Check if path is a directory
        if file_exists and os.path.isdir(path):
            return ToolResult.fail(f"Path is a directory, not a file: {path}")

        # Create backup if overwriting
        backup_path = None
        if is_overwrite and backup:
            backup_path = self._create_backup(path)

        # Write the file
        try:
            with open(path, 'w', encoding='utf-8') as f:
                f.write(content)
        except Exception as e:
            # Restore from backup if write failed
            if backup_path and os.path.exists(backup_path):
                shutil.copy2(backup_path, path)
            return ToolResult.fail(f"Failed to write file: {str(e)}")

        # Calculate stats
        line_count = content.count('\n') + (1 if content and not content.endswith('\n') else 0)
        char_count = len(content)

        action = "Overwrote" if is_overwrite else "Created"

        return ToolResult.ok(
            data={
                "path": path,
                "action": action.lower(),
                "lines": line_count,
                "characters": char_count,
                "backup_path": backup_path,
                "created_dirs": create_dirs and not os.path.exists(parent_dir) if parent_dir else False,
            },
            summary=f"{action} {path} ({line_count} lines, {char_count} chars)",
        )

    def _validate_write(self, path: str) -> Optional[str]:
        """Validate that we can write to this path."""
        # Check for dangerous paths
        if is_dangerous_path(path):
            return f"Cannot write to protected system path: {path}"

        # Check for dangerous extensions
        if has_dangerous_extension(path):
            _, ext = os.path.splitext(path)
            return f"Cannot create files with dangerous extension: {ext}"

        # Check parent directory is writable (if it exists)
        parent_dir = os.path.dirname(path)
        if parent_dir and os.path.exists(parent_dir):
            if not os.access(parent_dir, os.W_OK):
                return f"Directory not writable: {parent_dir}"

        return None

    def _create_backup(self, path: str) -> Optional[str]:
        """Create a backup of existing file."""
        try:
            backup_dir = os.path.join(os.path.dirname(path), '.ephraim_backups')
            os.makedirs(backup_dir, exist_ok=True)

            filename = os.path.basename(path)
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_filename = f"{filename}.{timestamp}.bak"
            backup_path = os.path.join(backup_dir, backup_filename)

            shutil.copy2(path, backup_path)
            return backup_path
        except Exception:
            return None


def write_file(path: str, content: str, create_dirs: bool = True) -> ToolResult:
    """Convenience function for writing files."""
    tool = WriteFileTool()
    return tool(path=path, content=content, create_dirs=create_dirs)
