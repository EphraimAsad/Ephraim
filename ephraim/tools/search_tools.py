"""
Search Tools

Provides glob and grep search capabilities.

- glob_search: Find files by pattern (like find or glob)
- grep_search: Search file contents (like grep or ripgrep)
"""

import os
import re
import fnmatch
from pathlib import Path
from typing import List, Optional, Dict, Any

from .base import BaseTool, ToolResult, ToolParam, ToolCategory, register_tool


# Directories to skip when searching
SKIP_DIRECTORIES = {
    '.git', '.svn', '.hg',  # Version control
    'node_modules', 'bower_components',  # JS dependencies
    '__pycache__', '.pytest_cache', '.mypy_cache',  # Python cache
    'venv', '.venv', 'env', '.env',  # Virtual environments
    'dist', 'build', 'target',  # Build outputs
    '.idea', '.vscode',  # IDE directories
    'coverage', '.coverage',  # Coverage reports
}

# Binary file extensions to skip for grep
BINARY_EXTENSIONS = {
    '.exe', '.dll', '.so', '.dylib', '.bin',
    '.zip', '.tar', '.gz', '.rar', '.7z',
    '.png', '.jpg', '.jpeg', '.gif', '.bmp', '.ico', '.webp',
    '.mp3', '.mp4', '.wav', '.avi', '.mkv',
    '.pdf', '.doc', '.docx', '.xls', '.xlsx',
    '.pyc', '.pyo', '.class', '.o', '.obj',
    '.woff', '.woff2', '.ttf', '.eot',
}


def should_skip_directory(dirname: str) -> bool:
    """Check if directory should be skipped."""
    return dirname.lower() in {d.lower() for d in SKIP_DIRECTORIES}


def is_binary_file(filepath: str) -> bool:
    """Check if file is likely binary based on extension."""
    _, ext = os.path.splitext(filepath.lower())
    return ext in BINARY_EXTENSIONS


@register_tool
class GlobSearchTool(BaseTool):
    """
    Search for files matching a glob pattern.

    Supports patterns like:
    - *.py (all Python files in current dir)
    - **/*.py (all Python files recursively)
    - src/**/*.ts (TypeScript files in src)
    - test_*.py (files starting with test_)
    """

    name = "glob_search"
    description = "Find files matching a glob pattern"
    category = ToolCategory.READ_ONLY  # No approval needed

    parameters = [
        ToolParam(
            name="pattern",
            type="string",
            description="Glob pattern (e.g., '**/*.py', 'src/*.ts')",
            required=True,
        ),
        ToolParam(
            name="path",
            type="string",
            description="Base directory to search from (default: current directory)",
            required=False,
            default=None,
        ),
        ToolParam(
            name="max_results",
            type="int",
            description="Maximum number of results to return",
            required=False,
            default=100,
        ),
        ToolParam(
            name="include_hidden",
            type="bool",
            description="Include hidden files/directories (starting with .)",
            required=False,
            default=False,
        ),
    ]

    def execute(self, **params) -> ToolResult:
        """Search for files matching the pattern."""
        pattern = params["pattern"]
        base_path = params.get("path") or os.getcwd()
        max_results = params.get("max_results", 100)
        include_hidden = params.get("include_hidden", False)

        # Resolve base path
        base_path = os.path.abspath(os.path.expanduser(base_path))

        if not os.path.exists(base_path):
            return ToolResult.fail(f"Path not found: {base_path}")

        if not os.path.isdir(base_path):
            return ToolResult.fail(f"Path is not a directory: {base_path}")

        # Use pathlib for glob
        try:
            base = Path(base_path)
            matches = []
            truncated = False

            for match in base.glob(pattern):
                # Skip hidden files unless requested
                if not include_hidden:
                    parts = match.relative_to(base).parts
                    if any(part.startswith('.') for part in parts):
                        continue

                # Skip directories in skip list
                if any(should_skip_directory(part) for part in match.parts):
                    continue

                matches.append(str(match))

                if len(matches) >= max_results:
                    truncated = True
                    break

            # Sort by modification time (most recent first)
            matches.sort(key=lambda x: os.path.getmtime(x) if os.path.exists(x) else 0, reverse=True)

            return ToolResult.ok(
                data={
                    "pattern": pattern,
                    "base_path": base_path,
                    "matches": matches,
                    "count": len(matches),
                    "truncated": truncated,
                },
                summary=f"Found {len(matches)} files matching '{pattern}'" +
                        (" (truncated)" if truncated else ""),
            )

        except Exception as e:
            return ToolResult.fail(f"Glob search failed: {str(e)}")


@register_tool
class GrepSearchTool(BaseTool):
    """
    Search for text patterns in files.

    Supports regex patterns and file filtering.
    Returns matching lines with context.
    """

    name = "grep_search"
    description = "Search for text patterns in file contents"
    category = ToolCategory.READ_ONLY  # No approval needed

    parameters = [
        ToolParam(
            name="pattern",
            type="string",
            description="Regex pattern to search for",
            required=True,
        ),
        ToolParam(
            name="path",
            type="string",
            description="File or directory to search (default: current directory)",
            required=False,
            default=None,
        ),
        ToolParam(
            name="include",
            type="string",
            description="File pattern to include (e.g., '*.py', '*.ts')",
            required=False,
            default=None,
        ),
        ToolParam(
            name="max_results",
            type="int",
            description="Maximum number of matching lines to return",
            required=False,
            default=50,
        ),
        ToolParam(
            name="context_lines",
            type="int",
            description="Number of context lines before/after match",
            required=False,
            default=0,
        ),
        ToolParam(
            name="case_sensitive",
            type="bool",
            description="Case-sensitive search",
            required=False,
            default=True,
        ),
    ]

    def execute(self, **params) -> ToolResult:
        """Search for pattern in files."""
        pattern = params["pattern"]
        search_path = params.get("path") or os.getcwd()
        include = params.get("include")
        max_results = params.get("max_results", 50)
        context_lines = params.get("context_lines", 0)
        case_sensitive = params.get("case_sensitive", True)

        # Resolve path
        search_path = os.path.abspath(os.path.expanduser(search_path))

        if not os.path.exists(search_path):
            return ToolResult.fail(f"Path not found: {search_path}")

        # Compile regex
        try:
            flags = 0 if case_sensitive else re.IGNORECASE
            regex = re.compile(pattern, flags)
        except re.error as e:
            return ToolResult.fail(f"Invalid regex pattern: {str(e)}")

        matches = []
        files_searched = 0
        files_with_matches = set()
        truncated = False

        # Get files to search
        if os.path.isfile(search_path):
            files_to_search = [search_path]
        else:
            files_to_search = self._get_files(search_path, include)

        for filepath in files_to_search:
            if len(matches) >= max_results:
                truncated = True
                break

            # Skip binary files
            if is_binary_file(filepath):
                continue

            files_searched += 1
            file_matches = self._search_file(
                filepath, regex, max_results - len(matches), context_lines
            )

            if file_matches:
                files_with_matches.add(filepath)
                matches.extend(file_matches)

        return ToolResult.ok(
            data={
                "pattern": pattern,
                "path": search_path,
                "matches": matches,
                "match_count": len(matches),
                "files_searched": files_searched,
                "files_with_matches": len(files_with_matches),
                "truncated": truncated,
            },
            summary=f"Found {len(matches)} matches in {len(files_with_matches)} files" +
                    (" (truncated)" if truncated else ""),
        )

    def _get_files(self, directory: str, include: Optional[str]) -> List[str]:
        """Get list of files to search."""
        files = []

        for root, dirs, filenames in os.walk(directory):
            # Skip hidden and excluded directories
            dirs[:] = [
                d for d in dirs
                if not d.startswith('.') and not should_skip_directory(d)
            ]

            for filename in filenames:
                # Skip hidden files
                if filename.startswith('.'):
                    continue

                # Apply include filter
                if include and not fnmatch.fnmatch(filename, include):
                    continue

                files.append(os.path.join(root, filename))

        return files

    def _search_file(
        self,
        filepath: str,
        regex: re.Pattern,
        max_matches: int,
        context_lines: int,
    ) -> List[Dict[str, Any]]:
        """Search a single file for matches."""
        matches = []

        try:
            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()
        except Exception:
            return []

        for line_num, line in enumerate(lines, 1):
            if len(matches) >= max_matches:
                break

            if regex.search(line):
                match_data = {
                    "file": filepath,
                    "line_number": line_num,
                    "line": line.rstrip('\n\r'),
                }

                # Add context if requested
                if context_lines > 0:
                    start = max(0, line_num - 1 - context_lines)
                    end = min(len(lines), line_num + context_lines)

                    match_data["context_before"] = [
                        lines[i].rstrip('\n\r')
                        for i in range(start, line_num - 1)
                    ]
                    match_data["context_after"] = [
                        lines[i].rstrip('\n\r')
                        for i in range(line_num, end)
                    ]

                matches.append(match_data)

        return matches


# Convenience functions
def glob_search(pattern: str, path: Optional[str] = None, max_results: int = 100) -> ToolResult:
    """Search for files matching a glob pattern."""
    tool = GlobSearchTool()
    return tool(pattern=pattern, path=path, max_results=max_results)


def grep_search(
    pattern: str,
    path: Optional[str] = None,
    include: Optional[str] = None,
    max_results: int = 50,
) -> ToolResult:
    """Search for text patterns in files."""
    tool = GrepSearchTool()
    return tool(pattern=pattern, path=path, include=include, max_results=max_results)
