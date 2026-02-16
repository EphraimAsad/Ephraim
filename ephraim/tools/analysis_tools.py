"""
Code Analysis Tools

Static code analysis and intelligence capabilities.

Commands:
- find_references: Find all usages of a symbol
- find_definition: Find where a symbol is defined
- analyze_imports: Analyze dependencies and imports
- dead_code_check: Find unused code
"""

import os
import re
import subprocess
from typing import Dict, Any, List, Optional, Set

from .base import BaseTool, ToolResult, ToolParam, ToolCategory, register_tool


def run_grep(
    pattern: str,
    path: str,
    file_types: Optional[List[str]] = None,
    context: int = 0,
) -> List[Dict[str, Any]]:
    """Run grep/ripgrep to find pattern matches."""
    matches = []

    # Try ripgrep first, fall back to grep
    try:
        cmd = ['rg', '--line-number', '--no-heading']
        if context > 0:
            cmd.extend(['-C', str(context)])
        if file_types:
            for ft in file_types:
                cmd.extend(['-g', f'*.{ft}'])
        cmd.extend([pattern, path])

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        output = result.stdout
    except FileNotFoundError:
        # Fall back to grep
        cmd = ['grep', '-rn']
        if context > 0:
            cmd.extend(['-C', str(context)])
        if file_types:
            include = ' '.join(f'--include=*.{ft}' for ft in file_types)
            cmd.extend(include.split())
        cmd.extend([pattern, path])

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        output = result.stdout
    except Exception:
        return matches

    # Parse output
    for line in output.split('\n'):
        if not line.strip():
            continue

        # Format: file:line:content
        parts = line.split(':', 2)
        if len(parts) >= 3:
            matches.append({
                "file": parts[0],
                "line": int(parts[1]) if parts[1].isdigit() else 0,
                "content": parts[2].strip(),
            })

    return matches


def get_file_extension(filepath: str) -> str:
    """Get file extension without dot."""
    return os.path.splitext(filepath)[1].lstrip('.')


def detect_language(filepath: str) -> str:
    """Detect programming language from file extension."""
    ext = get_file_extension(filepath)
    language_map = {
        "py": "python",
        "js": "javascript",
        "ts": "typescript",
        "jsx": "javascript",
        "tsx": "typescript",
        "go": "go",
        "rs": "rust",
        "rb": "ruby",
        "java": "java",
        "c": "c",
        "cpp": "cpp",
        "h": "c",
        "hpp": "cpp",
        "cs": "csharp",
    }
    return language_map.get(ext, "unknown")


@register_tool
class FindReferencesTool(BaseTool):
    """
    Find all references to a symbol (function, class, variable).
    """

    name = "find_references"
    description = "Find all usages of a symbol in the codebase"
    category = ToolCategory.READ_ONLY

    parameters = [
        ToolParam(
            name="symbol",
            type="string",
            description="Symbol name to find (function, class, variable)",
            required=True,
        ),
        ToolParam(
            name="path",
            type="string",
            description="Directory to search in",
            required=False,
            default=".",
        ),
        ToolParam(
            name="file_types",
            type="list",
            description="File extensions to search (e.g., ['py', 'js'])",
            required=False,
            default=None,
        ),
        ToolParam(
            name="include_definition",
            type="bool",
            description="Include definition in results",
            required=False,
            default=True,
        ),
    ]

    def execute(self, **params) -> ToolResult:
        """Find references."""
        symbol = params["symbol"]
        path = params.get("path", ".")
        file_types = params.get("file_types")
        include_definition = params.get("include_definition", True)

        # Build pattern for word boundary match
        pattern = rf'\b{re.escape(symbol)}\b'

        # Find matches
        matches = run_grep(pattern, path, file_types)

        # Categorize matches
        references: List[Dict[str, Any]] = []
        definitions: List[Dict[str, Any]] = []

        definition_patterns = [
            rf'def\s+{re.escape(symbol)}\s*\(',  # Python function
            rf'class\s+{re.escape(symbol)}[\s:(]',  # Python/JS class
            rf'function\s+{re.escape(symbol)}\s*\(',  # JS function
            rf'const\s+{re.escape(symbol)}\s*=',  # JS const
            rf'let\s+{re.escape(symbol)}\s*=',  # JS let
            rf'var\s+{re.escape(symbol)}\s*=',  # JS var
            rf'func\s+{re.escape(symbol)}\s*\(',  # Go function
            rf'type\s+{re.escape(symbol)}\s+',  # Go type
            rf'fn\s+{re.escape(symbol)}\s*[<(]',  # Rust function
            rf'struct\s+{re.escape(symbol)}\s*[{{<]',  # Rust/Go struct
        ]

        for match in matches:
            content = match["content"]
            is_definition = any(re.search(p, content) for p in definition_patterns)

            if is_definition:
                definitions.append(match)
            else:
                references.append(match)

        # Combine results
        if include_definition:
            all_refs = definitions + references
        else:
            all_refs = references

        return ToolResult.ok(
            data={
                "symbol": symbol,
                "total_references": len(references),
                "definitions": definitions[:10],
                "references": references[:50],
                "files_with_references": list(set(r["file"] for r in references))[:20],
            },
            summary=f"Found {len(definitions)} definition(s), {len(references)} reference(s) for '{symbol}'",
        )


@register_tool
class FindDefinitionTool(BaseTool):
    """
    Find where a symbol is defined.
    """

    name = "find_definition"
    description = "Find where a symbol is defined (function, class, variable)"
    category = ToolCategory.READ_ONLY

    parameters = [
        ToolParam(
            name="symbol",
            type="string",
            description="Symbol name to find definition for",
            required=True,
        ),
        ToolParam(
            name="path",
            type="string",
            description="Directory to search in",
            required=False,
            default=".",
        ),
        ToolParam(
            name="file_types",
            type="list",
            description="File extensions to search (e.g., ['py', 'js'])",
            required=False,
            default=None,
        ),
    ]

    # Definition patterns by language
    DEFINITION_PATTERNS = {
        "python": [
            r'def\s+{symbol}\s*\(',
            r'class\s+{symbol}[\s:(]',
            r'{symbol}\s*=\s*(?!.*==)',  # Assignment (not comparison)
        ],
        "javascript": [
            r'function\s+{symbol}\s*\(',
            r'const\s+{symbol}\s*=',
            r'let\s+{symbol}\s*=',
            r'var\s+{symbol}\s*=',
            r'class\s+{symbol}[\s{]',
            r'{symbol}\s*:\s*function',
            r'{symbol}\s*=\s*\([^)]*\)\s*=>',
        ],
        "typescript": [
            r'function\s+{symbol}\s*[<(]',
            r'const\s+{symbol}\s*[:<]?\s*=',
            r'let\s+{symbol}\s*[:<]?\s*=',
            r'class\s+{symbol}[\s<{]',
            r'interface\s+{symbol}[\s<{]',
            r'type\s+{symbol}\s*[<=]',
        ],
        "go": [
            r'func\s+{symbol}\s*\(',
            r'func\s+\([^)]+\)\s+{symbol}\s*\(',  # Method
            r'type\s+{symbol}\s+',
            r'var\s+{symbol}\s+',
            r'const\s+{symbol}\s*=',
        ],
        "rust": [
            r'fn\s+{symbol}\s*[<(]',
            r'struct\s+{symbol}[\s<{]',
            r'enum\s+{symbol}[\s<{]',
            r'trait\s+{symbol}[\s<{]',
            r'type\s+{symbol}\s*=',
            r'const\s+{symbol}\s*:',
            r'static\s+{symbol}\s*:',
        ],
    }

    def execute(self, **params) -> ToolResult:
        """Find definition."""
        symbol = params["symbol"]
        path = params.get("path", ".")
        file_types = params.get("file_types")

        definitions: List[Dict[str, Any]] = []

        # Try each language's definition patterns
        for lang, patterns in self.DEFINITION_PATTERNS.items():
            # Map language to file types
            lang_types = {
                "python": ["py"],
                "javascript": ["js", "jsx", "mjs"],
                "typescript": ["ts", "tsx"],
                "go": ["go"],
                "rust": ["rs"],
            }

            search_types = file_types or lang_types.get(lang, [])

            for pattern_template in patterns:
                pattern = pattern_template.format(symbol=re.escape(symbol))
                matches = run_grep(pattern, path, search_types, context=2)

                for match in matches:
                    # Verify it's actually a definition
                    if self._is_definition(match["content"], symbol, lang):
                        definitions.append({
                            **match,
                            "language": lang,
                            "type": self._get_definition_type(match["content"], symbol, lang),
                        })

        # Deduplicate
        seen = set()
        unique_defs = []
        for d in definitions:
            key = (d["file"], d["line"])
            if key not in seen:
                seen.add(key)
                unique_defs.append(d)

        if not unique_defs:
            return ToolResult.ok(
                data={
                    "symbol": symbol,
                    "found": False,
                    "definitions": [],
                },
                summary=f"No definition found for '{symbol}'",
            )

        return ToolResult.ok(
            data={
                "symbol": symbol,
                "found": True,
                "definitions": unique_defs[:10],
                "primary_definition": unique_defs[0] if unique_defs else None,
            },
            summary=f"Found {len(unique_defs)} definition(s) for '{symbol}' in {unique_defs[0]['file']}:{unique_defs[0]['line']}",
        )

    def _is_definition(self, content: str, symbol: str, language: str) -> bool:
        """Verify content is actually a definition."""
        # Check it's not just a usage
        usage_patterns = [
            rf'{symbol}\s*\(',  # Function call
            rf'\.{symbol}',  # Method call
            rf'import.*{symbol}',  # Import
        ]

        # Definition markers by language
        def_markers = {
            "python": ["def ", "class "],
            "javascript": ["function ", "const ", "let ", "var ", "class "],
            "typescript": ["function ", "const ", "let ", "class ", "interface ", "type "],
            "go": ["func ", "type ", "var ", "const "],
            "rust": ["fn ", "struct ", "enum ", "trait ", "type ", "const ", "static "],
        }

        markers = def_markers.get(language, [])
        return any(marker in content for marker in markers)

    def _get_definition_type(self, content: str, symbol: str, language: str) -> str:
        """Determine what type of definition this is."""
        type_markers = {
            "function": ["def ", "func ", "fn ", "function "],
            "class": ["class "],
            "struct": ["struct "],
            "interface": ["interface ", "trait "],
            "type": ["type "],
            "variable": ["const ", "let ", "var ", "static "],
            "enum": ["enum "],
        }

        for def_type, markers in type_markers.items():
            if any(marker in content for marker in markers):
                return def_type

        return "unknown"


@register_tool
class AnalyzeImportsTool(BaseTool):
    """
    Analyze imports and dependencies in a file or project.
    """

    name = "analyze_imports"
    description = "Analyze imports and dependencies"
    category = ToolCategory.READ_ONLY

    parameters = [
        ToolParam(
            name="file_path",
            type="string",
            description="File to analyze (or directory for project-wide)",
            required=True,
        ),
        ToolParam(
            name="include_stdlib",
            type="bool",
            description="Include standard library imports",
            required=False,
            default=False,
        ),
    ]

    # Standard library patterns
    STDLIB = {
        "python": [
            "os", "sys", "re", "json", "typing", "collections", "itertools",
            "functools", "pathlib", "datetime", "time", "math", "random",
            "subprocess", "threading", "multiprocessing", "logging", "unittest",
            "dataclasses", "enum", "abc", "contextlib", "copy", "io", "string",
        ],
        "javascript": [
            "fs", "path", "http", "https", "crypto", "util", "events",
            "stream", "buffer", "os", "child_process", "url", "querystring",
        ],
    }

    def execute(self, **params) -> ToolResult:
        """Analyze imports."""
        file_path = params["file_path"]
        include_stdlib = params.get("include_stdlib", False)

        if os.path.isdir(file_path):
            return self._analyze_directory(file_path, include_stdlib)
        else:
            return self._analyze_file(file_path, include_stdlib)

    def _analyze_file(self, file_path: str, include_stdlib: bool) -> ToolResult:
        """Analyze imports in a single file."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except Exception as e:
            return ToolResult.fail(f"Could not read file: {str(e)}")

        language = detect_language(file_path)
        imports = self._extract_imports(content, language)

        # Filter stdlib if requested
        if not include_stdlib:
            stdlib = self.STDLIB.get(language, [])
            imports = [i for i in imports if i["module"].split(".")[0] not in stdlib]

        # Categorize
        local_imports = [i for i in imports if i.get("is_relative", False)]
        external_imports = [i for i in imports if not i.get("is_relative", False)]

        return ToolResult.ok(
            data={
                "file": file_path,
                "language": language,
                "total_imports": len(imports),
                "local_imports": local_imports,
                "external_imports": external_imports,
                "dependencies": list(set(i["module"].split(".")[0] for i in external_imports)),
            },
            summary=f"Found {len(imports)} imports ({len(local_imports)} local, {len(external_imports)} external)",
        )

    def _analyze_directory(self, dir_path: str, include_stdlib: bool) -> ToolResult:
        """Analyze imports across a directory."""
        all_imports: Dict[str, int] = {}
        files_analyzed = 0

        for root, _, files in os.walk(dir_path):
            for filename in files:
                ext = get_file_extension(filename)
                if ext not in ['py', 'js', 'ts', 'jsx', 'tsx']:
                    continue

                file_path = os.path.join(root, filename)
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()

                    language = detect_language(file_path)
                    imports = self._extract_imports(content, language)

                    for imp in imports:
                        module = imp["module"].split(".")[0]
                        if not include_stdlib:
                            stdlib = self.STDLIB.get(language, [])
                            if module in stdlib:
                                continue
                        all_imports[module] = all_imports.get(module, 0) + 1

                    files_analyzed += 1
                except Exception:
                    continue

        # Sort by usage count
        sorted_imports = sorted(all_imports.items(), key=lambda x: x[1], reverse=True)

        return ToolResult.ok(
            data={
                "directory": dir_path,
                "files_analyzed": files_analyzed,
                "unique_dependencies": len(all_imports),
                "dependencies": [{"module": k, "count": v} for k, v in sorted_imports[:50]],
            },
            summary=f"Analyzed {files_analyzed} files, found {len(all_imports)} unique dependencies",
        )

    def _extract_imports(self, content: str, language: str) -> List[Dict[str, Any]]:
        """Extract imports from source code."""
        imports = []

        if language == "python":
            # import x / from x import y
            import_pattern = r'^(?:from\s+(\S+)\s+)?import\s+(.+?)(?:\s+as\s+\S+)?$'
            for line in content.split('\n'):
                line = line.strip()
                match = re.match(import_pattern, line)
                if match:
                    from_module = match.group(1)
                    imported = match.group(2)

                    if from_module:
                        imports.append({
                            "module": from_module,
                            "imports": [i.strip() for i in imported.split(',')],
                            "is_relative": from_module.startswith('.'),
                        })
                    else:
                        for mod in imported.split(','):
                            mod = mod.strip().split(' as ')[0]
                            imports.append({
                                "module": mod,
                                "imports": [],
                                "is_relative": False,
                            })

        elif language in ["javascript", "typescript"]:
            # import x from 'y' / require('y')
            import_patterns = [
                r"import\s+(?:[\w{},\s*]+\s+from\s+)?['\"]([^'\"]+)['\"]",
                r"require\s*\(\s*['\"]([^'\"]+)['\"]\s*\)",
            ]

            for pattern in import_patterns:
                for match in re.finditer(pattern, content):
                    module = match.group(1)
                    imports.append({
                        "module": module,
                        "is_relative": module.startswith('.'),
                    })

        return imports


@register_tool
class DeadCodeCheckTool(BaseTool):
    """
    Find potentially unused code (functions, classes, variables).
    """

    name = "dead_code_check"
    description = "Find potentially unused code"
    category = ToolCategory.READ_ONLY

    parameters = [
        ToolParam(
            name="path",
            type="string",
            description="Directory to analyze",
            required=False,
            default=".",
        ),
        ToolParam(
            name="file_types",
            type="list",
            description="File extensions to check (e.g., ['py', 'js'])",
            required=False,
            default=["py"],
        ),
    ]

    def execute(self, **params) -> ToolResult:
        """Check for dead code."""
        path = params.get("path", ".")
        file_types = params.get("file_types", ["py"])

        # Collect all definitions
        definitions: List[Dict[str, Any]] = []

        for ft in file_types:
            # Find definitions
            def_patterns = self._get_definition_patterns(ft)

            for pattern_info in def_patterns:
                matches = run_grep(pattern_info["pattern"], path, [ft])

                for match in matches:
                    # Extract symbol name
                    content = match["content"]
                    symbol_match = re.search(pattern_info["extract"], content)
                    if symbol_match:
                        definitions.append({
                            "symbol": symbol_match.group(1),
                            "type": pattern_info["type"],
                            "file": match["file"],
                            "line": match["line"],
                        })

        # Check each definition for references
        potentially_unused: List[Dict[str, Any]] = []

        for defn in definitions:
            symbol = defn["symbol"]

            # Skip common patterns that are always "used"
            if symbol.startswith('_') or symbol in ['__init__', 'main', 'setUp', 'tearDown']:
                continue

            # Count references
            pattern = rf'\b{re.escape(symbol)}\b'
            matches = run_grep(pattern, path, file_types)

            # Subtract 1 for the definition itself
            reference_count = len(matches) - 1

            if reference_count <= 0:
                potentially_unused.append({
                    **defn,
                    "references": reference_count,
                    "confidence": "high" if reference_count == 0 else "medium",
                })

        # Sort by confidence and type
        potentially_unused.sort(key=lambda x: (x["confidence"], x["type"]))

        return ToolResult.ok(
            data={
                "total_definitions": len(definitions),
                "potentially_unused": len(potentially_unused),
                "unused_items": potentially_unused[:50],
                "by_type": self._group_by_type(potentially_unused),
            },
            summary=f"Found {len(potentially_unused)} potentially unused items out of {len(definitions)} definitions",
        )

    def _get_definition_patterns(self, file_type: str) -> List[Dict[str, Any]]:
        """Get definition patterns for a file type."""
        patterns = {
            "py": [
                {"pattern": r'def\s+\w+\s*\(', "extract": r'def\s+(\w+)', "type": "function"},
                {"pattern": r'class\s+\w+[\s:(]', "extract": r'class\s+(\w+)', "type": "class"},
            ],
            "js": [
                {"pattern": r'function\s+\w+\s*\(', "extract": r'function\s+(\w+)', "type": "function"},
                {"pattern": r'const\s+\w+\s*=', "extract": r'const\s+(\w+)', "type": "variable"},
                {"pattern": r'class\s+\w+[\s{]', "extract": r'class\s+(\w+)', "type": "class"},
            ],
            "ts": [
                {"pattern": r'function\s+\w+\s*[<(]', "extract": r'function\s+(\w+)', "type": "function"},
                {"pattern": r'const\s+\w+\s*[:<]?\s*=', "extract": r'const\s+(\w+)', "type": "variable"},
                {"pattern": r'class\s+\w+[\s<{]', "extract": r'class\s+(\w+)', "type": "class"},
                {"pattern": r'interface\s+\w+[\s<{]', "extract": r'interface\s+(\w+)', "type": "interface"},
            ],
        }
        return patterns.get(file_type, patterns["py"])

    def _group_by_type(self, items: List[Dict[str, Any]]) -> Dict[str, int]:
        """Group items by type."""
        by_type: Dict[str, int] = {}
        for item in items:
            t = item["type"]
            by_type[t] = by_type.get(t, 0) + 1
        return by_type


# Convenience functions

def find_references(symbol: str, path: str = ".", file_types: Optional[List[str]] = None) -> Dict[str, Any]:
    """Find references to a symbol."""
    tool = FindReferencesTool()
    result = tool(symbol=symbol, path=path, file_types=file_types)
    return result.data if result.success else {"error": result.error}


def find_definition(symbol: str, path: str = ".", file_types: Optional[List[str]] = None) -> Dict[str, Any]:
    """Find definition of a symbol."""
    tool = FindDefinitionTool()
    result = tool(symbol=symbol, path=path, file_types=file_types)
    return result.data if result.success else {"error": result.error}


def analyze_imports(file_path: str, include_stdlib: bool = False) -> Dict[str, Any]:
    """Analyze imports in a file or directory."""
    tool = AnalyzeImportsTool()
    result = tool(file_path=file_path, include_stdlib=include_stdlib)
    return result.data if result.success else {"error": result.error}


def dead_code_check(path: str = ".", file_types: Optional[List[str]] = None) -> Dict[str, Any]:
    """Check for dead code."""
    tool = DeadCodeCheckTool()
    result = tool(path=path, file_types=file_types or ["py"])
    return result.data if result.success else {"error": result.error}
