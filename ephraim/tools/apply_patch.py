"""
Apply Patch Tool (Patch Engine)

Critical safety component for code modifications.
Uses find/replace patches instead of full file rewrites.

Safety requirements:
- Must confirm single exact match before patching
- Reject ambiguous edits (multiple matches)
- Fail safely with clear error
- Create backup before patching
"""

import os
import shutil
from datetime import datetime
from typing import Optional, Tuple

from .base import BaseTool, ToolResult, ToolParam, ToolCategory, register_tool


class PatchError(Exception):
    """Raised when patch application fails."""
    pass


@register_tool
class ApplyPatchTool(BaseTool):
    """
    Apply a find/replace patch to a file.

    This tool is the ONLY way Ephraim modifies code.
    It uses surgical find/replace patches instead of full file rewrites.

    Safety features:
    - Requires exact single match (no ambiguity)
    - Creates backup before modification
    - Validates file exists and is readable
    - Returns clear error messages
    """

    name = "apply_patch"
    description = "Apply a find/replace patch to modify a file"
    category = ToolCategory.EXECUTION  # Requires approval

    parameters = [
        ToolParam(
            name="path",
            type="string",
            description="Path to the file to patch",
            required=True,
        ),
        ToolParam(
            name="find",
            type="string",
            description="Exact string to find in the file",
            required=True,
        ),
        ToolParam(
            name="replace",
            type="string",
            description="String to replace the found text with",
            required=True,
        ),
        ToolParam(
            name="create_backup",
            type="bool",
            description="Whether to create a backup file",
            required=False,
            default=True,
        ),
    ]

    def execute(self, **params) -> ToolResult:
        """Apply the patch to the file."""
        path = params["path"]
        find_str = params["find"]
        replace_str = params["replace"]
        create_backup = params.get("create_backup", True)

        # Resolve path
        path = os.path.abspath(os.path.expanduser(path))

        # Validation
        validation_error = self._validate_patch(path, find_str, replace_str)
        if validation_error:
            return ToolResult.fail(validation_error)

        # Read the file
        try:
            with open(path, 'r', encoding='utf-8') as f:
                content = f.read()
        except Exception as e:
            return ToolResult.fail(f"Failed to read file: {str(e)}")

        # Count occurrences
        count = content.count(find_str)

        if count == 0:
            return ToolResult.fail(
                f"Pattern not found in file.\n"
                f"Searched for:\n{self._truncate(find_str, 200)}"
            )

        if count > 1:
            return ToolResult.fail(
                f"Ambiguous patch: found {count} occurrences of the pattern.\n"
                f"Pattern:\n{self._truncate(find_str, 200)}\n\n"
                f"Provide more context to make the match unique."
            )

        # Create backup if requested
        backup_path = None
        if create_backup:
            backup_path = self._create_backup(path)
            if backup_path is None:
                return ToolResult.fail("Failed to create backup file")

        # Apply the patch
        new_content = content.replace(find_str, replace_str, 1)

        # Write the result
        try:
            with open(path, 'w', encoding='utf-8') as f:
                f.write(new_content)
        except Exception as e:
            # Try to restore from backup
            if backup_path and os.path.exists(backup_path):
                shutil.copy2(backup_path, path)
            return ToolResult.fail(f"Failed to write file: {str(e)}")

        # Calculate diff info
        find_lines = find_str.count('\n') + 1
        replace_lines = replace_str.count('\n') + 1
        line_diff = replace_lines - find_lines

        # Find the line number of the change
        line_number = content[:content.find(find_str)].count('\n') + 1

        return ToolResult.ok(
            data={
                "path": path,
                "backup_path": backup_path,
                "line_number": line_number,
                "lines_removed": find_lines,
                "lines_added": replace_lines,
                "line_diff": line_diff,
                "find_preview": self._truncate(find_str, 100),
                "replace_preview": self._truncate(replace_str, 100),
            },
            summary=f"Patched {path} at line {line_number} "
                    f"({line_diff:+d} lines)",
        )

    def _validate_patch(
        self,
        path: str,
        find_str: str,
        replace_str: str,
    ) -> Optional[str]:
        """
        Validate patch parameters.

        Returns error message or None if valid.
        """
        # Check file exists
        if not os.path.exists(path):
            return f"File not found: {path}"

        # Check it's a file
        if not os.path.isfile(path):
            return f"Not a file: {path}"

        # Check file is readable
        if not os.access(path, os.R_OK):
            return f"File not readable: {path}"

        # Check file is writable
        if not os.access(path, os.W_OK):
            return f"File not writable: {path}"

        # Check find string is not empty
        if not find_str:
            return "Find string cannot be empty"

        # Check that find and replace are different
        if find_str == replace_str:
            return "Find and replace strings are identical - no change needed"

        return None

    def _create_backup(self, path: str) -> Optional[str]:
        """
        Create a backup of the file.

        Returns the backup path or None if failed.
        """
        try:
            # Create backup directory
            backup_dir = os.path.join(os.path.dirname(path), '.ephraim_backups')
            os.makedirs(backup_dir, exist_ok=True)

            # Generate backup filename with timestamp
            filename = os.path.basename(path)
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_filename = f"{filename}.{timestamp}.bak"
            backup_path = os.path.join(backup_dir, backup_filename)

            # Copy the file
            shutil.copy2(path, backup_path)
            return backup_path

        except Exception:
            return None

    @staticmethod
    def _truncate(text: str, max_length: int) -> str:
        """Truncate text for display."""
        if len(text) <= max_length:
            return text
        return text[:max_length] + "..."


def preview_patch(
    path: str,
    find_str: str,
    replace_str: str,
    context_lines: int = 3,
) -> Tuple[bool, str]:
    """
    Preview a patch without applying it.

    Returns:
        Tuple of (can_apply, preview_text)
    """
    path = os.path.abspath(os.path.expanduser(path))

    if not os.path.exists(path):
        return False, f"File not found: {path}"

    try:
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception as e:
        return False, f"Failed to read file: {str(e)}"

    count = content.count(find_str)

    if count == 0:
        return False, "Pattern not found in file"

    if count > 1:
        return False, f"Ambiguous: found {count} occurrences"

    # Find position and line number
    pos = content.find(find_str)
    lines = content.split('\n')
    line_count = 0
    char_count = 0

    for i, line in enumerate(lines):
        char_count += len(line) + 1  # +1 for newline
        if char_count > pos:
            line_count = i
            break

    # Get context
    start_line = max(0, line_count - context_lines)
    end_line = min(len(lines), line_count + find_str.count('\n') + context_lines + 1)

    preview_lines = []
    preview_lines.append(f"--- {path} (original)")
    preview_lines.append(f"+++ {path} (patched)")
    preview_lines.append(f"@@ -{start_line + 1},{end_line - start_line} @@")

    # Show before context
    for i in range(start_line, line_count):
        preview_lines.append(f"  {lines[i]}")

    # Show removed lines
    for line in find_str.split('\n'):
        preview_lines.append(f"- {line}")

    # Show added lines
    for line in replace_str.split('\n'):
        preview_lines.append(f"+ {line}")

    # Show after context
    after_start = line_count + find_str.count('\n') + 1
    for i in range(after_start, end_line):
        if i < len(lines):
            preview_lines.append(f"  {lines[i]}")

    return True, '\n'.join(preview_lines)
