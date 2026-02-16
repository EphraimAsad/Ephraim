#!/usr/bin/env python3
"""
Ephraim Planning Model Fine-Tuning Script
==========================================
Generates 500,000 training examples for the planning model (Ike-coder:14b).

The planning model ONLY proposes plans with action="propose_plan".
It never executes tools directly.

NEW: Includes multi-agent coordination training (~25K examples).
The model learns when/how to spawn parallel agents for efficiency.

Run this on Google Colab with A100 GPU (40GB VRAM).
"""

import json
import random
import os
from typing import List, Dict, Any, Tuple
from dataclasses import dataclass

# =============================================================================
# PLANNING TASK TEMPLATES - 100+ Base Templates
# =============================================================================

# Category 1: Python Development (20 templates)
PYTHON_TASKS = [
    ("Create a CLI calculator that supports add, subtract, multiply, divide", "CLI calculator",
     ["Create calculator.py with arithmetic functions", "Add main() with input loop", "Add error handling for invalid input", "Test all operations"]),
    ("Build a todo list application with file persistence", "todo app",
     ["Create todo.py with Task class", "Implement add/remove/list functions", "Add JSON file persistence", "Create CLI interface"]),
    ("Create a password generator with customizable options", "password generator",
     ["Create password_gen.py", "Add character set options (uppercase, lowercase, numbers, symbols)", "Implement secure random generation", "Add CLI arguments with argparse"]),
    ("Build a simple web scraper for extracting links", "web scraper",
     ["Create scraper.py with requests", "Add HTML parsing with BeautifulSoup", "Implement link extraction", "Add output formatting"]),
    ("Create a file organizer that sorts files by extension", "file organizer",
     ["Create organizer.py", "Add file type detection", "Implement folder creation logic", "Add move/copy functionality"]),
    ("Build a countdown timer with notification", "countdown timer",
     ["Create timer.py", "Add time parsing (HH:MM:SS)", "Implement countdown loop with display", "Add completion notification"]),
    ("Create a unit converter for length/weight/temperature", "unit converter",
     ["Create converter.py", "Add conversion functions for each unit type", "Implement unit detection", "Create interactive CLI"]),
    ("Build a simple quiz application", "quiz app",
     ["Create quiz.py with Question class", "Load questions from JSON file", "Implement scoring system", "Add result display"]),
    ("Create a markdown to HTML converter", "markdown converter",
     ["Create md_converter.py", "Implement basic markdown parsing", "Generate HTML output", "Add file I/O"]),
    ("Build a simple HTTP server", "HTTP server",
     ["Create server.py using http.server", "Add request routing", "Implement response handling", "Add static file serving"]),
    ("Create a log file analyzer", "log analyzer",
     ["Create analyzer.py", "Parse log file format", "Extract statistics (errors, warnings)", "Generate summary report"]),
    ("Build a CSV to JSON converter", "CSV converter",
     ["Create csv_json.py", "Parse CSV with headers", "Convert to JSON structure", "Add CLI for input/output files"]),
    ("Create a backup script with compression", "backup script",
     ["Create backup.py", "Implement file discovery", "Add ZIP compression", "Include timestamp in backup name"]),
    ("Build a contact book application", "contact book",
     ["Create contacts.py with Contact class", "Implement CRUD operations", "Add search functionality", "Persist to JSON file"]),
    ("Create a simple encryption/decryption tool", "encryption tool",
     ["Create crypto.py", "Implement Caesar cipher", "Add encrypt/decrypt functions", "Create CLI interface"]),
    ("Build a weather display using API", "weather app",
     ["Create weather.py", "Add API client for weather service", "Parse JSON response", "Format display output"]),
    ("Create a pomodoro timer", "pomodoro timer",
     ["Create pomodoro.py", "Implement 25/5 minute cycles", "Add session tracking", "Include break notifications"]),
    ("Build a URL shortener service", "URL shortener",
     ["Create shortener.py", "Implement hash-based shortening", "Add URL storage (JSON/SQLite)", "Create lookup function"]),
    ("Create a duplicate file finder", "duplicate finder",
     ["Create dupfinder.py", "Implement file hashing (MD5/SHA)", "Find matching hashes", "Report duplicates"]),
    ("Build a simple note-taking app", "notes app",
     ["Create notes.py", "Implement create/read/update/delete", "Add tagging system", "Store in markdown files"]),
]

# Category 2: Bug Fixing (15 templates)
BUG_FIX_TASKS = [
    ("Fix the TypeError in the calculate function", "TypeError fix",
     ["Read the file to understand current code", "Identify the type mismatch", "Add type conversion or validation", "Test the fix"]),
    ("Debug why the loop runs infinitely", "infinite loop fix",
     ["Read the code with the loop", "Identify missing break condition", "Add proper termination logic", "Verify loop terminates"]),
    ("Fix the IndexError when accessing list elements", "IndexError fix",
     ["Read the code causing the error", "Add bounds checking", "Handle edge case of empty list", "Test with various inputs"]),
    ("Resolve the import error for missing module", "import fix",
     ["Check current imports", "Identify missing dependency", "Add to requirements.txt", "Update import statement"]),
    ("Fix the division by zero error", "division fix",
     ["Read the division code", "Add zero check before division", "Return appropriate value or raise error", "Test edge cases"]),
    ("Debug the function returning None unexpectedly", "None return fix",
     ["Read the function code", "Trace all return paths", "Add missing return statement", "Test all branches"]),
    ("Fix the file not found error", "file path fix",
     ["Check file path construction", "Verify file exists", "Add path validation", "Handle missing file gracefully"]),
    ("Resolve the JSON parsing error", "JSON fix",
     ["Read the JSON handling code", "Validate JSON structure", "Add try/except for parsing", "Handle malformed JSON"]),
    ("Fix the encoding error when reading file", "encoding fix",
     ["Check file reading code", "Add encoding parameter (utf-8)", "Handle different encodings", "Test with various files"]),
    ("Debug the recursive function causing stack overflow", "recursion fix",
     ["Read the recursive function", "Add base case if missing", "Check recursion depth", "Consider iterative approach"]),
    ("Fix the attribute error on object access", "attribute fix",
     ["Read the class/object code", "Check attribute initialization", "Add hasattr check or default", "Test object creation"]),
    ("Resolve the permission denied error", "permission fix",
     ["Check file access code", "Verify file permissions", "Add permission check before access", "Handle access denied"]),
    ("Fix the memory leak in long-running process", "memory fix",
     ["Read the process code", "Identify objects not being released", "Add proper cleanup", "Test memory usage"]),
    ("Debug the race condition in threaded code", "threading fix",
     ["Read the threaded code", "Identify shared resources", "Add proper locking", "Test concurrent access"]),
    ("Fix the incorrect output format", "output fix",
     ["Read the output generation code", "Compare with expected format", "Fix formatting logic", "Test output matches spec"]),
]

# Category 3: Refactoring (15 templates)
REFACTOR_TASKS = [
    ("Extract the validation logic into a separate function", "extract function",
     ["Read the code with validation", "Identify validation logic to extract", "Create new validation function", "Update original code to use it"]),
    ("Rename the poorly named variables to be more descriptive", "rename variables",
     ["Read the code", "Identify unclear variable names", "Choose descriptive names", "Rename consistently throughout"]),
    ("Split the large function into smaller functions", "split function",
     ["Read the large function", "Identify logical sections", "Create separate functions for each", "Compose them in main function"]),
    ("Convert the class to use dataclass", "dataclass conversion",
     ["Read the current class", "Identify data attributes", "Convert to @dataclass", "Update any custom __init__"]),
    ("Add type hints to the module", "add type hints",
     ["Read the module code", "Identify function signatures", "Add parameter and return types", "Add typing imports if needed"]),
    ("Replace magic numbers with named constants", "magic numbers",
     ["Read the code", "Identify hardcoded numbers", "Create named constants", "Replace numbers with constants"]),
    ("Convert callbacks to async/await", "async conversion",
     ["Read the callback code", "Identify async operations", "Convert to async functions", "Update callers to await"]),
    ("Simplify the nested conditionals", "simplify conditions",
     ["Read the nested if/else", "Identify guard clauses", "Use early returns", "Flatten the structure"]),
    ("Extract common code into a base class", "base class extraction",
     ["Read the classes with duplication", "Identify common methods", "Create base class", "Inherit from base"]),
    ("Convert the module to use dependency injection", "dependency injection",
     ["Read the module", "Identify hard dependencies", "Add constructor parameters", "Update instantiation"]),
    ("Replace print statements with proper logging", "add logging",
     ["Read the code with prints", "Import logging module", "Configure logger", "Replace prints with log calls"]),
    ("Convert dictionary access to use .get() with defaults", "safe dict access",
     ["Read dict access code", "Identify direct key access", "Replace with .get(key, default)", "Test with missing keys"]),
    ("Organize imports according to PEP 8", "organize imports",
     ["Read current imports", "Group: stdlib, third-party, local", "Sort alphabetically within groups", "Add blank lines between groups"]),
    ("Add docstrings to all public functions", "add docstrings",
     ["Read the public functions", "Write descriptive docstrings", "Include Args, Returns, Raises", "Follow Google/NumPy style"]),
    ("Convert string concatenation to f-strings", "f-string conversion",
     ["Read string operations", "Identify concatenation and .format()", "Convert to f-strings", "Test output unchanged"]),
]

# Category 4: Testing (15 templates)
TESTING_TASKS = [
    ("Add unit tests for the calculator functions", "calculator tests",
     ["Create test_calculator.py", "Test each arithmetic function", "Add edge cases (zero, negative)", "Test error handling"]),
    ("Write integration tests for the API endpoints", "API tests",
     ["Create test_api.py", "Test each endpoint", "Mock external dependencies", "Verify response format"]),
    ("Add pytest fixtures for database tests", "pytest fixtures",
     ["Create conftest.py", "Add database fixture", "Add cleanup teardown", "Use in test files"]),
    ("Create mock objects for external service calls", "create mocks",
     ["Identify external calls", "Create mock classes", "Configure mock responses", "Use in tests"]),
    ("Fix the failing test for user authentication", "fix failing test",
     ["Read the failing test", "Identify assertion failure", "Fix test or implementation", "Verify test passes"]),
    ("Add test coverage for error handling paths", "error path tests",
     ["Identify error handling code", "Write tests that trigger errors", "Verify error responses", "Check exception handling"]),
    ("Create parameterized tests for validation", "parameterized tests",
     ["Identify validation function", "Create test parameters", "Use @pytest.mark.parametrize", "Test all parameter combinations"]),
    ("Add performance benchmarks", "performance tests",
     ["Identify critical functions", "Create benchmark tests", "Measure execution time", "Set baseline thresholds"]),
    ("Write tests for the new feature", "feature tests",
     ["Understand feature requirements", "Create test cases", "Test happy path and edge cases", "Add regression tests"]),
    ("Add snapshot tests for CLI output", "snapshot tests",
     ["Capture current CLI output", "Create snapshot test", "Compare against baseline", "Update snapshots when needed"]),
    ("Create test data fixtures", "test data",
     ["Identify test data needs", "Create fixture files (JSON/CSV)", "Load in test setup", "Clean up after tests"]),
    ("Add timeout tests for long operations", "timeout tests",
     ["Identify long-running operations", "Add timeout decorators", "Test timeout behavior", "Verify graceful handling"]),
    ("Write tests for concurrent access", "concurrency tests",
     ["Identify shared resources", "Create concurrent test scenarios", "Use threading in tests", "Verify thread safety"]),
    ("Add property-based tests with hypothesis", "property tests",
     ["Import hypothesis", "Define property strategies", "Write property-based tests", "Find edge cases automatically"]),
    ("Create end-to-end test for user workflow", "e2e tests",
     ["Map user workflow steps", "Create test that follows flow", "Verify final state", "Test complete journey"]),
]

# Category 5: API Development (10 templates)
API_TASKS = [
    ("Create a REST API endpoint for user registration", "user registration API",
     ["Create users route", "Add POST /register endpoint", "Validate input data", "Return user object or error"]),
    ("Add authentication middleware", "auth middleware",
     ["Create auth middleware", "Verify JWT token", "Extract user from token", "Block unauthorized requests"]),
    ("Implement pagination for list endpoints", "pagination",
     ["Add page/limit parameters", "Implement offset calculation", "Add total count to response", "Return paginated results"]),
    ("Add rate limiting to API", "rate limiting",
     ["Create rate limit middleware", "Track request counts", "Return 429 when exceeded", "Add rate limit headers"]),
    ("Create webhook handler endpoint", "webhook handler",
     ["Create webhook route", "Verify webhook signature", "Parse webhook payload", "Process event asynchronously"]),
    ("Add OpenAPI/Swagger documentation", "API documentation",
     ["Add docstrings to endpoints", "Configure swagger generator", "Define request/response schemas", "Generate API docs"]),
    ("Implement file upload endpoint", "file upload",
     ["Create upload route", "Handle multipart form data", "Validate file type and size", "Save file and return URL"]),
    ("Add search endpoint with filters", "search endpoint",
     ["Create search route", "Parse query parameters", "Build filter query", "Return matching results"]),
    ("Create batch processing endpoint", "batch endpoint",
     ["Create batch route", "Accept array of operations", "Process each operation", "Return batch results"]),
    ("Implement caching for expensive endpoints", "API caching",
     ["Identify cacheable endpoints", "Add cache middleware", "Set cache TTL", "Invalidate on updates"]),
]

# Category 6: Database (10 templates)
DATABASE_TASKS = [
    ("Create database model for users", "user model",
     ["Create User model class", "Define fields (id, email, password_hash)", "Add timestamps", "Create migration"]),
    ("Add database migration for new column", "migration",
     ["Create migration file", "Add new column definition", "Handle existing data", "Test rollback"]),
    ("Implement database connection pooling", "connection pool",
     ["Configure connection pool", "Set pool size limits", "Handle connection errors", "Add connection timeout"]),
    ("Add database indexes for query optimization", "add indexes",
     ["Identify slow queries", "Determine index columns", "Create index migration", "Verify query performance"]),
    ("Create database backup script", "db backup",
     ["Create backup script", "Export database to file", "Compress backup", "Add rotation/cleanup"]),
    ("Implement soft delete for records", "soft delete",
     ["Add deleted_at column", "Modify delete to set timestamp", "Filter out deleted in queries", "Add restore function"]),
    ("Add database transaction handling", "transactions",
     ["Wrap operations in transaction", "Handle commit/rollback", "Add savepoints if needed", "Handle nested transactions"]),
    ("Create data seeding script", "seed data",
     ["Create seed script", "Define seed data", "Handle existing data", "Add CLI command"]),
    ("Implement database audit logging", "audit log",
     ["Create audit log table", "Log create/update/delete", "Include user and timestamp", "Add query for history"]),
    ("Add full-text search capability", "full-text search",
     ["Add search index", "Implement search query", "Handle relevance ranking", "Return highlighted results"]),
]

# Category 7: Frontend (10 templates)
FRONTEND_TASKS = [
    ("Create a React component for login form", "login form",
     ["Create LoginForm.jsx", "Add email and password fields", "Implement form validation", "Handle submit with API call"]),
    ("Build a responsive navigation menu", "nav menu",
     ["Create Navbar component", "Add menu items", "Implement mobile hamburger", "Add active state styling"]),
    ("Add form validation with error messages", "form validation",
     ["Read form component", "Add validation rules", "Display error messages", "Disable submit until valid"]),
    ("Create a data table with sorting", "data table",
     ["Create Table component", "Add column headers", "Implement sort on click", "Show sort indicators"]),
    ("Implement infinite scroll for list", "infinite scroll",
     ["Create scroll container", "Detect scroll position", "Load more data on threshold", "Show loading indicator"]),
    ("Add dark mode toggle", "dark mode",
     ["Create theme context", "Add theme toggle button", "Apply CSS variables", "Persist preference"]),
    ("Create modal dialog component", "modal component",
     ["Create Modal component", "Add overlay backdrop", "Handle close on escape/click outside", "Add animation"]),
    ("Implement drag and drop list", "drag and drop",
     ["Create DraggableList component", "Add drag handlers", "Update order on drop", "Persist new order"]),
    ("Add loading skeleton screens", "skeleton loading",
     ["Create Skeleton component", "Match content layout", "Add animation", "Replace with content on load"]),
    ("Create toast notification system", "toast notifications",
     ["Create Toast component", "Add toast context", "Implement auto-dismiss", "Add different types (success, error)"]),
]

# Category 8: DevOps (10 templates)
DEVOPS_TASKS = [
    ("Create a Dockerfile for the application", "Dockerfile",
     ["Create Dockerfile", "Choose base image", "Copy source and install deps", "Configure entrypoint"]),
    ("Set up GitHub Actions CI workflow", "CI workflow",
     ["Create .github/workflows/ci.yml", "Add test job", "Add lint job", "Configure triggers"]),
    ("Create docker-compose for local development", "docker-compose",
     ["Create docker-compose.yml", "Add app service", "Add database service", "Configure networking"]),
    ("Add environment configuration management", "env config",
     ["Create .env.example", "Add config loading", "Validate required vars", "Document variables"]),
    ("Create deployment script", "deploy script",
     ["Create deploy.sh", "Add build step", "Push to server/registry", "Run migrations"]),
    ("Set up pre-commit hooks", "pre-commit",
     ["Create .pre-commit-config.yaml", "Add linting hooks", "Add formatting hooks", "Test hook execution"]),
    ("Create Kubernetes deployment manifest", "k8s deployment",
     ["Create deployment.yaml", "Define replicas and resources", "Add health checks", "Configure secrets"]),
    ("Add monitoring and health checks", "health checks",
     ["Create health endpoint", "Check dependencies", "Return health status", "Configure monitoring"]),
    ("Set up log aggregation", "log aggregation",
     ["Configure structured logging", "Set up log shipping", "Add correlation IDs", "Create log queries"]),
    ("Create infrastructure as code", "terraform",
     ["Create terraform files", "Define resources", "Add variables", "Output connection info"]),
]

# Category 9: Security (5 templates)
SECURITY_TASKS = [
    ("Fix SQL injection vulnerability", "SQL injection fix",
     ["Read the database query code", "Identify string concatenation", "Replace with parameterized queries", "Test with injection attempts"]),
    ("Add input sanitization", "input sanitization",
     ["Identify user inputs", "Add sanitization functions", "Escape special characters", "Validate input format"]),
    ("Implement CSRF protection", "CSRF protection",
     ["Add CSRF token generation", "Include token in forms", "Verify token on submit", "Handle token mismatch"]),
    ("Add password hashing", "password hashing",
     ["Import bcrypt/argon2", "Hash passwords on registration", "Compare hash on login", "Handle migration of old passwords"]),
    ("Implement rate limiting for login", "login rate limit",
     ["Track failed login attempts", "Lock after N failures", "Add unlock timeout", "Log suspicious activity"]),
]

# Category 10: Performance (5 templates)
PERFORMANCE_TASKS = [
    ("Optimize slow database query", "query optimization",
     ["Profile the slow query", "Analyze execution plan", "Add indexes or rewrite query", "Verify performance improvement"]),
    ("Add caching layer", "add caching",
     ["Identify cacheable data", "Implement cache get/set", "Add cache invalidation", "Test cache hit rate"]),
    ("Implement lazy loading", "lazy loading",
     ["Identify heavy resources", "Defer loading until needed", "Add loading placeholders", "Test performance"]),
    ("Reduce bundle size", "bundle optimization",
     ["Analyze bundle contents", "Remove unused dependencies", "Add code splitting", "Verify size reduction"]),
    ("Add request compression", "compression",
     ["Enable gzip compression", "Configure compression middleware", "Set compression level", "Test compressed responses"]),
]

# =============================================================================
# MULTI-AGENT COORDINATION PATTERNS (NEW - 25K examples target)
# =============================================================================

# Pattern 1: Parallel exploration - spawn multiple EXPLORE agents
PARALLEL_EXPLORE_TASKS = [
    ("Implement user profile feature across full stack",
     "full-stack user profile",
     ["Spawn EXPLORE agent to analyze frontend structure",
      "Spawn EXPLORE agent to analyze backend API patterns",
      "Wait for both agents to complete",
      "Design unified implementation based on findings",
      "Spawn parallel EXECUTE agents for frontend and backend",
      "Integrate and test"],
     {"parallel_agents": ["frontend_explorer", "backend_explorer"], "coordination": "wait_all"}),

    ("Add search functionality to the e-commerce app",
     "e-commerce search",
     ["Spawn EXPLORE agent to analyze product database schema",
      "Spawn EXPLORE agent to find existing search implementations",
      "Wait for exploration results",
      "Design search feature based on findings",
      "Implement search backend",
      "Add search UI"],
     {"parallel_agents": ["db_explorer", "code_explorer"], "coordination": "wait_all"}),

    ("Migrate database from MySQL to PostgreSQL",
     "database migration",
     ["Spawn EXPLORE agent to analyze current MySQL schema",
      "Spawn EXPLORE agent to find all database queries in codebase",
      "Wait for both analyses",
      "Create PostgreSQL schema migration plan",
      "Generate migration scripts",
      "Update application code"],
     {"parallel_agents": ["schema_explorer", "query_explorer"], "coordination": "wait_all"}),

    ("Implement real-time notifications across web and mobile",
     "cross-platform notifications",
     ["Spawn EXPLORE agent to analyze web notification system",
      "Spawn EXPLORE agent to analyze mobile push setup",
      "Wait for exploration",
      "Design unified notification architecture",
      "Implement shared notification service",
      "Integrate with both platforms"],
     {"parallel_agents": ["web_explorer", "mobile_explorer"], "coordination": "wait_all"}),

    ("Unify authentication between microservices",
     "auth unification",
     ["Spawn EXPLORE agent to analyze Service A auth",
      "Spawn EXPLORE agent to analyze Service B auth",
      "Spawn EXPLORE agent to analyze Service C auth",
      "Wait for all explorations",
      "Design centralized auth service",
      "Implement auth gateway"],
     {"parallel_agents": ["service_a_explorer", "service_b_explorer", "service_c_explorer"], "coordination": "wait_all"}),
]

# Pattern 2: Sequential agent delegation - research then execute
SEQUENTIAL_AGENT_TASKS = [
    ("Refactor deprecated function with many usages",
     "safe refactoring",
     ["Spawn RESEARCH agent to analyze all usages of deprecated function",
      "Wait for research results",
      "Create migration plan based on findings",
      "Spawn EXECUTE agent to update each file systematically",
      "Run tests to verify"],
     {"sequential_agents": ["research_impact", "execute_migration"], "coordination": "sequential"}),

    ("Optimize slow API endpoint",
     "API optimization",
     ["Spawn RESEARCH agent to profile endpoint performance",
      "Wait for profiling results",
      "Identify bottlenecks from analysis",
      "Spawn EXECUTE agent to implement optimizations",
      "Benchmark improvements"],
     {"sequential_agents": ["profile_analysis", "implement_fixes"], "coordination": "sequential"}),

    ("Fix security vulnerability across codebase",
     "security fix",
     ["Spawn RESEARCH agent to scan for all vulnerable patterns",
      "Wait for security scan results",
      "Prioritize fixes by severity",
      "Spawn EXECUTE agents to patch each vulnerability",
      "Run security tests"],
     {"sequential_agents": ["security_scan", "patch_vulnerabilities"], "coordination": "sequential"}),

    ("Update deprecated library throughout project",
     "library update",
     ["Spawn RESEARCH agent to find all usages of old library",
      "Wait for usage report",
      "Check compatibility with new version",
      "Spawn EXECUTE agent to update imports and calls",
      "Test for regressions"],
     {"sequential_agents": ["find_usages", "update_code"], "coordination": "sequential"}),

    ("Implement feature flag system",
     "feature flags",
     ["Spawn RESEARCH agent to analyze current config system",
      "Wait for analysis",
      "Design feature flag architecture",
      "Spawn EXECUTE agent to implement flag service",
      "Add flags to existing features"],
     {"sequential_agents": ["analyze_config", "implement_flags"], "coordination": "sequential"}),
]

# Pattern 3: Parallel execution - multiple independent changes
PARALLEL_EXECUTE_TASKS = [
    ("Update UI components to new design system",
     "design system migration",
     ["Read new design system guidelines",
      "Spawn EXECUTE agent to update Header component",
      "Spawn EXECUTE agent to update Sidebar component",
      "Spawn EXECUTE agent to update Footer component",
      "Wait for all updates",
      "Test visual consistency"],
     {"parallel_agents": ["header_updater", "sidebar_updater", "footer_updater"], "coordination": "wait_all"}),

    ("Add logging to all API endpoints",
     "API logging",
     ["Define logging format and levels",
      "Spawn EXECUTE agent to add logging to /users endpoints",
      "Spawn EXECUTE agent to add logging to /products endpoints",
      "Spawn EXECUTE agent to add logging to /orders endpoints",
      "Wait for all additions",
      "Verify log output"],
     {"parallel_agents": ["users_logging", "products_logging", "orders_logging"], "coordination": "wait_all"}),

    ("Implement i18n across the application",
     "internationalization",
     ["Set up i18n framework",
      "Spawn EXECUTE agent to extract strings from frontend",
      "Spawn EXECUTE agent to extract strings from email templates",
      "Wait for extractions",
      "Create translation files"],
     {"parallel_agents": ["frontend_i18n", "email_i18n"], "coordination": "wait_all"}),
]

# Pattern 4: Research-heavy tasks - multiple research agents
MULTI_RESEARCH_TASKS = [
    ("Evaluate best caching strategy for the app",
     "caching evaluation",
     ["Spawn RESEARCH agent to analyze Redis options",
      "Spawn RESEARCH agent to analyze Memcached options",
      "Spawn RESEARCH agent to analyze in-memory options",
      "Wait for all research",
      "Compare findings and recommend",
      "Implement chosen strategy"],
     {"parallel_agents": ["redis_research", "memcached_research", "inmemory_research"], "coordination": "wait_all"}),

    ("Choose testing framework for new project",
     "testing framework",
     ["Spawn RESEARCH agent to evaluate pytest",
      "Spawn RESEARCH agent to evaluate unittest",
      "Spawn RESEARCH agent to evaluate nose2",
      "Wait for evaluations",
      "Recommend based on project needs",
      "Set up chosen framework"],
     {"parallel_agents": ["pytest_eval", "unittest_eval", "nose_eval"], "coordination": "wait_all"}),
]

# Pattern 5: Hybrid coordination - mix of strategies
HYBRID_AGENT_TASKS = [
    ("Complete system audit and modernization",
     "system modernization",
     ["Spawn parallel EXPLORE agents for frontend, backend, and database",
      "Wait for initial exploration",
      "Spawn RESEARCH agent to analyze findings and prioritize",
      "Wait for prioritization",
      "Spawn parallel EXECUTE agents for high-priority items",
      "Integrate and test"],
     {"parallel_agents": ["explore_frontend", "explore_backend", "explore_db"],
      "sequential_agents": ["research_priorities"], "coordination": "hybrid"}),

    ("Implement multi-tenant support",
     "multi-tenancy",
     ["Spawn EXPLORE agents to analyze data model and auth system",
      "Wait for exploration",
      "Spawn RESEARCH agent to design tenant isolation",
      "Wait for design",
      "Spawn parallel EXECUTE agents for data and auth changes",
      "Test tenant isolation"],
     {"parallel_agents": ["explore_data", "explore_auth", "exec_data", "exec_auth"],
      "sequential_agents": ["design_isolation"], "coordination": "hybrid"}),
]

# Combine all multi-agent tasks
ALL_MULTI_AGENT_TASKS = (
    PARALLEL_EXPLORE_TASKS +
    SEQUENTIAL_AGENT_TASKS +
    PARALLEL_EXECUTE_TASKS +
    MULTI_RESEARCH_TASKS +
    HYBRID_AGENT_TASKS
)

# Combine all task categories
ALL_PLANNING_TASKS = (
    PYTHON_TASKS +
    BUG_FIX_TASKS +
    REFACTOR_TASKS +
    TESTING_TASKS +
    API_TASKS +
    DATABASE_TASKS +
    FRONTEND_TASKS +
    DEVOPS_TASKS +
    SECURITY_TASKS +
    PERFORMANCE_TASKS
)

# =============================================================================
# AUGMENTATION STRATEGIES
# =============================================================================

TASK_PREFIXES = [
    "Create", "Build", "Implement", "Design", "Develop", "Make", "Write",
    "Add", "Set up", "Configure", "Generate", "Construct", "Establish"
]

TASK_SUFFIXES = [
    " using Python", " in Python", " with standard library",
    " from scratch", " for the terminal", " as a CLI tool",
    " with best practices", " following PEP 8", " with type hints",
    " with error handling", " with tests", " with documentation",
    "", "", "", ""  # Empty suffixes for variety
]

LANGUAGE_VARIATIONS = [
    ("Python", ["python", "py", "Python 3", "python3"]),
    ("JavaScript", ["javascript", "js", "node", "nodejs"]),
    ("TypeScript", ["typescript", "ts"]),
    ("React", ["react", "React.js", "reactjs"]),
    ("API", ["REST API", "api", "web service", "endpoint"]),
]

CONFIDENCE_LEVELS = {
    "high": (85, 98),
    "medium": (65, 84),
    "low": (40, 64),
}

RISK_WEIGHTS = {
    "LOW": 0.6,
    "MEDIUM": 0.3,
    "HIGH": 0.1,
}

# =============================================================================
# EXAMPLE GENERATION
# =============================================================================

def generate_planning_example(
    task: str,
    topic: str,
    steps: List[str],
    add_detail: bool = False
) -> Dict[str, Any]:
    """Generate a single planning training example.

    Returns pre-formatted text for faster dataset processing (no map needed).
    """

    # Determine risk and confidence
    risk = random.choices(
        ["LOW", "MEDIUM", "HIGH"],
        weights=[0.6, 0.3, 0.1]
    )[0]

    conf_range = CONFIDENCE_LEVELS["high"] if risk == "LOW" else CONFIDENCE_LEVELS["medium"]
    confidence = random.randint(*conf_range)

    # Generate detailed reasoning
    reasoning_templates = [
        f"The user wants to {task.lower()}. I will create a {topic} with the necessary components.",
        f"I need to {task.lower()}. This requires implementing a {topic} that handles the core functionality.",
        f"To accomplish this task, I'll build a {topic}. Let me break this down into clear steps.",
        f"The request is to {task.lower()}. I'll approach this by creating a {topic} with proper structure.",
        f"I understand the user needs a {topic}. I'll implement this step by step with proper error handling.",
    ]

    if add_detail:
        reasoning_templates = [
            f"The user wants to {task.lower()}. Let me analyze the requirements: (1) Core functionality for {topic}, (2) Error handling for edge cases, (3) Clean code structure. I will create a {topic} with these components.",
            f"I need to {task.lower()}. Breaking this down: First, I'll set up the basic structure. Then add the core logic. Finally, implement error handling and testing. This will result in a robust {topic}.",
            f"To accomplish this task, I'll build a {topic}. Key considerations: maintainability, error handling, and user experience. Let me plan the implementation steps carefully.",
        ]

    reasoning = random.choice(reasoning_templates)

    # Vary the steps slightly
    final_steps = steps.copy()
    if random.random() > 0.7:
        final_steps.append(f"Document the {topic}")
    if random.random() > 0.8:
        final_steps.append(f"Add comments explaining key logic")

    # Build the output
    output = {
        "reasoning": reasoning,
        "confidence": confidence,
        "risk": risk,
        "action": "propose_plan",
        "plan": {
            "goal_understanding": task,
            "execution_steps": final_steps,
            "validation_plan": f"Test the {topic} manually to verify all features work correctly",
            "git_strategy": f"Single commit: Add {topic}"
        }
    }

    output_json = json.dumps(output)

    # Pre-format the text field for faster training (skip dataset.map())
    text = f"""### Instruction:
{task}

### Response:
{output_json}"""

    return {
        "instruction": task,
        "input": "",
        "output": output_json,
        "text": text  # Pre-formatted for training
    }


def generate_clarification_example(task: str, question: str) -> Dict[str, Any]:
    """Generate an example where the model asks for clarification."""

    output = {
        "reasoning": f"The request to {task.lower()} is unclear. I need more information before proposing a plan.",
        "confidence": random.randint(30, 55),
        "risk": "LOW",
        "action": "ask_user",
        "params": {
            "question": question
        }
    }

    output_json = json.dumps(output)

    # Pre-format text field
    text = f"""### Instruction:
{task}

### Response:
{output_json}"""

    return {
        "instruction": task,
        "input": "",
        "output": output_json,
        "text": text
    }


def generate_multi_agent_example(
    task: str,
    topic: str,
    steps: List[str],
    agent_strategy: Dict[str, Any],
) -> Dict[str, Any]:
    """Generate a multi-agent coordination planning example."""

    # Determine coordination type and reasoning
    coord_type = agent_strategy.get("coordination", "wait_all")
    parallel_agents = agent_strategy.get("parallel_agents", [])
    sequential_agents = agent_strategy.get("sequential_agents", [])

    if coord_type == "wait_all":
        reasoning = f"This task requires {task.lower()}. I'll spawn parallel agents to handle each component independently for efficiency. Using {len(parallel_agents)} parallel agents: {', '.join(parallel_agents)}."
    elif coord_type == "sequential":
        reasoning = f"This is a complex task requiring {task.lower()}. I'll first spawn a RESEARCH agent to analyze impact, then proceed based on findings. Sequential agents: {', '.join(sequential_agents)}."
    else:  # hybrid
        reasoning = f"This task requires {task.lower()} with both parallel exploration and sequential planning. I'll use a hybrid strategy with {len(parallel_agents)} parallel agents and sequential coordination."

    # Risk is usually MEDIUM for multi-agent tasks
    risk = random.choice(["MEDIUM", "MEDIUM", "HIGH"])
    confidence = random.randint(75, 92)

    output = {
        "reasoning": reasoning,
        "confidence": confidence,
        "risk": risk,
        "action": "propose_plan",
        "plan": {
            "goal_understanding": task,
            "execution_steps": steps,
            "validation_plan": f"Verify all agents completed successfully and {topic} is fully implemented",
            "git_strategy": f"Atomic commits per component, final merge commit for {topic}",
            "agent_strategy": agent_strategy
        }
    }

    output_json = json.dumps(output)
    text = f"""### Instruction:
{task}

### Response:
{output_json}"""

    return {
        "instruction": task,
        "input": "",
        "output": output_json,
        "text": text
    }


def generate_parallel_spawn_example(task: str, agents: List[str], agent_type: str = "EXPLORE") -> Dict[str, Any]:
    """Generate example where model decides to spawn multiple parallel agents."""

    reasoning_templates = [
        f"This task requires analyzing multiple components. I'll spawn {len(agents)} parallel {agent_type} agents to gather information efficiently.",
        f"To {task.lower()}, I need to understand multiple parts of the codebase. Spawning parallel agents for each area.",
        f"For efficiency, I'll use {len(agents)} parallel agents to explore {', '.join(agents)} simultaneously.",
    ]

    output = {
        "reasoning": random.choice(reasoning_templates),
        "confidence": random.randint(80, 95),
        "risk": "MEDIUM",
        "action": "propose_plan",
        "plan": {
            "goal_understanding": task,
            "execution_steps": [
                f"Spawn {agent_type} agent for {agent}" for agent in agents
            ] + ["Wait for all agents to complete", "Synthesize findings", "Implement based on results"],
            "validation_plan": "Verify all agents completed and findings are coherent",
            "git_strategy": "Single commit after all parallel work completes",
            "agent_strategy": {
                "parallel_agents": agents,
                "coordination": "wait_all"
            }
        }
    }

    output_json = json.dumps(output)
    text = f"""### Instruction:
{task}

### Response:
{output_json}"""

    return {
        "instruction": task,
        "input": "",
        "output": output_json,
        "text": text
    }


def generate_sequential_delegation_example(task: str, research_task: str, execute_task: str) -> Dict[str, Any]:
    """Generate example of sequential agent delegation (research then execute)."""

    reasoning = f"This requires careful analysis before action. I'll first spawn a RESEARCH agent to {research_task.lower()}, then spawn EXECUTE agent to {execute_task.lower()} based on findings."

    output = {
        "reasoning": reasoning,
        "confidence": random.randint(82, 94),
        "risk": "MEDIUM",
        "action": "propose_plan",
        "plan": {
            "goal_understanding": task,
            "execution_steps": [
                f"Spawn RESEARCH agent to {research_task}",
                "Wait for research results",
                "Analyze findings and plan execution",
                f"Spawn EXECUTE agent to {execute_task}",
                "Verify changes and test"
            ],
            "validation_plan": "Verify research-informed execution completed correctly",
            "git_strategy": "Commit after research, commit after execution",
            "agent_strategy": {
                "sequential_agents": ["research", "execute"],
                "coordination": "sequential"
            }
        }
    }

    output_json = json.dumps(output)
    text = f"""### Instruction:
{task}

### Response:
{output_json}"""

    return {
        "instruction": task,
        "input": "",
        "output": output_json,
        "text": text
    }


def augment_task(task: str, topic: str, steps: List[str]) -> Tuple[str, str, List[str]]:
    """Augment a task with variations."""

    # Vary prefix
    words = task.split()
    if words[0].lower() in [p.lower() for p in TASK_PREFIXES]:
        words[0] = random.choice(TASK_PREFIXES)

    # Add suffix
    suffix = random.choice(TASK_SUFFIXES)
    new_task = " ".join(words) + suffix

    # Vary steps
    new_steps = steps.copy()
    random.shuffle(new_steps)  # Slight reorder

    return new_task, topic, new_steps


def generate_planning_dataset(num_examples: int = 500000) -> List[Dict[str, Any]]:
    """Generate the full planning training dataset.

    Dataset composition for 500K examples:
    - Core task plans: ~200K (40%)
    - Detailed reasoning: ~100K (20%)
    - Clarification scenarios: ~50K (10%)
    - Complex multi-file plans: ~100K (20%)
    - Multi-agent coordination plans (NEW): ~25K (5%)
    - Edge cases: ~25K (5%)
    """

    examples = []

    print(f"Generating {num_examples} planning examples...")

    # Add base examples first
    print("  Adding core planning examples...")
    for task, topic, steps in ALL_PLANNING_TASKS:
        examples.append(generate_planning_example(task, topic, steps))
        examples.append(generate_planning_example(task, topic, steps, add_detail=True))

    # Add multi-agent coordination examples (NEW - 5% = 25K)
    print("  Adding multi-agent coordination examples...")
    multi_agent_target = num_examples // 20  # 5% = 25K

    # Add base multi-agent examples
    for task, topic, steps, strategy in ALL_MULTI_AGENT_TASKS:
        examples.append(generate_multi_agent_example(task, topic, steps, strategy))

    # Add parallel spawn variations
    parallel_spawn_scenarios = [
        ("Analyze frontend, backend, and database architecture", ["frontend", "backend", "database"]),
        ("Audit authentication across all services", ["user_service", "auth_service", "api_gateway"]),
        ("Find all uses of deprecated API in codebase", ["controllers", "services", "utils"]),
        ("Map dependencies between modules", ["core_module", "plugins", "extensions"]),
        ("Review code quality in each layer", ["presentation", "business", "data"]),
        ("Analyze test coverage gaps", ["unit_tests", "integration_tests", "e2e_tests"]),
        ("Explore microservices communication patterns", ["service_a", "service_b", "message_queue"]),
        ("Audit logging across application layers", ["api_layer", "service_layer", "db_layer"]),
    ]

    for task, agents in parallel_spawn_scenarios:
        for agent_type in ["EXPLORE", "RESEARCH"]:
            examples.append(generate_parallel_spawn_example(task, agents, agent_type))

    # Add sequential delegation variations
    sequential_scenarios = [
        ("Refactor user authentication module",
         "analyze all authentication usages and patterns",
         "update authentication code with new patterns"),
        ("Migrate from REST to GraphQL",
         "identify all REST endpoints and their consumers",
         "implement GraphQL equivalents"),
        ("Update error handling strategy",
         "catalog all error handling patterns in codebase",
         "standardize error handling"),
        ("Implement caching layer",
         "profile application hotspots and cache candidates",
         "add caching to identified areas"),
        ("Optimize database queries",
         "identify slow queries and their causes",
         "optimize query patterns"),
        ("Add comprehensive logging",
         "audit current logging coverage",
         "add structured logging"),
        ("Implement rate limiting",
         "analyze endpoint traffic patterns",
         "add rate limiting middleware"),
        ("Upgrade framework version",
         "identify breaking changes and deprecations",
         "update code for new version"),
    ]

    for task, research, execute in sequential_scenarios:
        examples.append(generate_sequential_delegation_example(task, research, execute))

    # Fill multi-agent examples to target
    while len([e for e in examples if "agent_strategy" in e.get("output", "")]) < multi_agent_target:
        if random.random() > 0.5:
            task, topic, steps, strategy = random.choice(ALL_MULTI_AGENT_TASKS)
            examples.append(generate_multi_agent_example(task, topic, steps, strategy))
        elif random.random() > 0.5:
            task, agents = random.choice(parallel_spawn_scenarios)
            examples.append(generate_parallel_spawn_example(task, agents, random.choice(["EXPLORE", "RESEARCH"])))
        else:
            task, research, execute = random.choice(sequential_scenarios)
            examples.append(generate_sequential_delegation_example(task, research, execute))

    # Add clarification examples (10% = 50K)
    print("  Adding clarification examples...")
    clarification_questions = [
        ("Create an application", "What type of application do you need? CLI, web, or desktop?"),
        ("Build a tool", "What specific functionality should the tool provide?"),
        ("Implement a feature", "Could you provide more details about the expected behavior?"),
        ("Fix the bug", "Can you describe the bug and when it occurs?"),
        ("Add functionality", "What exactly should this functionality do?"),
        ("Optimize the code", "Which specific part of the code needs optimization?"),
        ("Update the system", "What changes should be made to the system?"),
        ("Create a script", "What should the script accomplish?"),
        ("Modify the behavior", "What is the current behavior and what should it become?"),
        ("Implement the logic", "Can you describe the expected logic in more detail?"),
        ("Set up the infrastructure", "What infrastructure components do you need?"),
        ("Deploy the application", "Which environment should we deploy to?"),
        ("Integrate with external service", "Which external service should we integrate with?"),
        ("Improve performance", "Which specific metrics need improvement?"),
        ("Add security measures", "What security requirements must be met?"),
    ]

    clarification_target = num_examples // 10  # 10% = 50K
    while len([e for e in examples if "ask_user" in e.get("output", "")]) < clarification_target:
        task, question = random.choice(clarification_questions)
        examples.append(generate_clarification_example(task, question))

    # Fill remaining with augmented core examples
    print("  Augmenting to reach target...")
    while len(examples) < num_examples:
        task, topic, steps = random.choice(ALL_PLANNING_TASKS)
        new_task, new_topic, new_steps = augment_task(task, topic, steps)

        # Decide if detailed reasoning (50% chance)
        add_detail = random.random() > 0.5

        examples.append(generate_planning_example(new_task, new_topic, new_steps, add_detail))

        if len(examples) % 50000 == 0:
            print(f"  Generated {len(examples)} examples...")

    random.shuffle(examples)
    return examples[:num_examples]


# =============================================================================
# TRAINING
# =============================================================================

def save_dataset(examples: List[Dict[str, Any]], filename: str):
    """Save dataset to JSONL file."""
    with open(filename, "w", encoding="utf-8") as f:
        for example in examples:
            f.write(json.dumps(example) + "\n")
    print(f"Saved {len(examples)} examples to {filename}")


def train_planning_model(
    dataset_path: str = "planning_training.jsonl",
    output_name: str = "Ike-coder-14b",
    model_name: str = "unsloth/Qwen2.5-Coder-14B-Instruct",
    max_steps: int = 5000,
):
    """Fine-tune the planning model."""
    from unsloth import FastLanguageModel
    from datasets import load_dataset
    from trl import SFTTrainer
    from transformers import TrainingArguments

    print(f"\n{'='*60}")
    print(f"Training Planning Model: {output_name}")
    print(f"Base model: {model_name}")
    print(f"{'='*60}\n")

    # Load model with 4-bit quantization
    print("Loading model...")
    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name=model_name,
        max_seq_length=4096,
        load_in_4bit=True,
        dtype=None,
    )

    # Add LoRA adapters with higher rank for better capacity
    print("Adding LoRA adapters (rank=32)...")
    model = FastLanguageModel.get_peft_model(
        model,
        r=32,
        lora_alpha=32,
        lora_dropout=0,
        target_modules=[
            "q_proj", "k_proj", "v_proj", "o_proj",
            "gate_proj", "up_proj", "down_proj",
        ],
        bias="none",
        use_gradient_checkpointing="unsloth",
        random_state=42,
    )

    # Load dataset - text field is pre-formatted for speed
    print(f"Loading dataset from {dataset_path}...")
    dataset = load_dataset("json", data_files=dataset_path, split="train")

    # Note: We skip dataset.map() because text is already formatted
    # This significantly speeds up processing for 500K examples
    print(f"Dataset size: {len(dataset)} examples")

    # Training arguments optimized for A100 GPU
    training_args = TrainingArguments(
        output_dir=f"outputs/{output_name}",
        per_device_train_batch_size=4,
        gradient_accumulation_steps=4,
        warmup_ratio=0.1,
        max_steps=max_steps,
        learning_rate=1e-4,
        fp16=False,
        bf16=True,
        logging_steps=100,
        save_steps=500,
        optim="adamw_8bit",
        weight_decay=0.01,
        lr_scheduler_type="cosine",
        seed=42,
    )

    # Create trainer
    trainer = SFTTrainer(
        model=model,
        tokenizer=tokenizer,
        train_dataset=dataset,
        dataset_text_field="text",
        max_seq_length=4096,
        args=training_args,
    )

    # Train
    print("Starting training...")
    trainer.train()

    # Export to GGUF
    print(f"\nExporting {output_name} to GGUF (Q4_K_M)...")
    model.save_pretrained_gguf(
        output_name,
        tokenizer,
        quantization_method="q4_k_m",
    )

    print(f"\nTraining complete: {output_name}")
    return model, tokenizer


def create_modelfile():
    """Create Ollama Modelfile for the planning model."""

    modelfile = '''FROM ./Ike-coder-14b-unsloth.Q4_K_M.gguf

PARAMETER temperature 0.1
PARAMETER top_p 0.9
PARAMETER stop "### Instruction:"
PARAMETER stop "### Response:"

SYSTEM """You are Ephraim's planning model (Ike-coder). You ONLY propose execution plans.

REQUIRED OUTPUT FORMAT (JSON):
{"reasoning": "your analysis", "confidence": 0-100, "risk": "LOW|MEDIUM|HIGH", "action": "propose_plan", "plan": {"goal_understanding": "...", "execution_steps": ["step1", "step2", ...], "validation_plan": "...", "git_strategy": "...", "agent_strategy": {...}}}

MULTI-AGENT COORDINATION:
For complex tasks, include agent_strategy in your plan:
- parallel_agents: ["agent1", "agent2"] - for independent work
- sequential_agents: ["research", "execute"] - for dependent work
- coordination: "wait_all" | "sequential" | "hybrid"

Agent types: EXPLORE, PLAN, EXECUTE, RESEARCH

Example agent_strategy:
{"parallel_agents": ["frontend_explorer", "backend_explorer"], "coordination": "wait_all"}

RULES:
- action MUST be "propose_plan" (you cannot execute tools)
- Include clear, actionable execution_steps
- For multi-component tasks, spawn parallel agents
- For research-then-act tasks, use sequential agents
- Set confidence based on how well you understand the task

If uncertain (confidence < 60), use:
{"reasoning": "Need clarification", "confidence": 40, "risk": "LOW", "action": "ask_user", "params": {"question": "Your question"}}"""
'''

    with open("Modelfile.plan", "w") as f:
        f.write(modelfile)
    print("Created: Modelfile.plan")


def main():
    """Main entry point."""
    import os

    # Disable wandb
    os.environ["WANDB_DISABLED"] = "true"

    print("="*60)
    print("IKE-CODER PLANNING MODEL FINE-TUNING")
    print("="*60)
    print(f"\nGenerating 500,000 planning training examples...")
    print("Base model: qwen2.5-coder:14b")
    print("Output: Ike-coder:14b")
    print("GPU: A100 (batch_size=4, effective_batch=16)")
    print("="*60 + "\n")

    # Generate dataset
    examples = generate_planning_dataset(500000)
    save_dataset(examples, "planning_training.jsonl")

    # Train model
    train_planning_model(
        dataset_path="planning_training.jsonl",
        output_name="Ike-coder-14b",
        max_steps=5000,
    )

    # Create modelfile
    create_modelfile()

    print("\n" + "="*60)
    print("IKE-CODER TRAINING COMPLETE!")
    print("="*60)
    print("\nNext steps:")
    print("1. Download Ike-coder-14b-unsloth.Q4_K_M.gguf")
    print("2. Download Modelfile.plan")
    print("3. Run: ollama create Ike-coder:14b -f Modelfile.plan")
    print("="*60)


if __name__ == "__main__":
    main()
