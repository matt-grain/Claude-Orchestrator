# Debussy Refactoring Plan

**Created:** 2026-01-15
**Based on:** CODE_REVIEW_REPORT.md
**Reviewer:** Textual TUI Expert

---

## Summary Tracking Table

| # | Task | Priority | Effort | Quick Win | Status |
|---|------|----------|--------|-----------|--------|
| 1 | Define OrchestratorUI Protocol | High | Low | Yes | ✅ Done |
| 2 | Extract Docker/Path Utilities | High | Low | Yes | ✅ Done |
| 3 | Add ClaudeRunner Callback Setter | Medium | Low | Yes | ✅ Done |
| 4 | Replace assert with RuntimeError | Medium | Low | Yes | ✅ Done |
| 5 | Refactor PIDRegistry Singleton | Medium | Low | Yes | ✅ Done |
| 6 | Extract ClaudeRunner Components | High | High | No | ✅ Partial (see [notes](../notes/NOTES_phase3_templates_phase_5.md)) |
| 7 | Add Constants Module | Low | Low | Yes | ⬜ Pending |
| 8 | Consolidate Log Method Names | Low | Low | Yes | ⬜ Pending |

---

## Deferred/Disagreed Items

### CLI Complexity (Finding #2)
**Assessment:** Disagree with priority. The CLI module complexity is acceptable for a Click-based command interface. The `audit()` and `run()` functions are complex because they handle many flags and user interactions, but they are linear and readable. Extracting them into command classes would add indirection without improving testability since Click already provides good testing utilities via `CliRunner`. This is cosmetic refactoring that can wait.

### Mutable Token Statistics (Finding #8)
**Assessment:** Partially disagree. The current token tracking in `OrchestrationController.update_token_stats()` is actually correct for its purpose:
- Session tokens are intentionally overwritten (they represent cumulative session totals from Claude's API)
- Run totals are accumulated only when `cost > 0` because that is when Claude's final result arrives

The immutable accumulator pattern suggested would require storing every single token update (potentially hundreds per phase) just to sum them later. The current approach is more memory-efficient. However, adding a brief comment explaining the logic would be worthwhile.

### Bare Exception Handler (Finding #9)
**Assessment:** Already acceptable. The exception in `cli.py:585-586` is in a non-critical display path where failing to parse phase details should not crash the CLI. Adding debug logging is minor polish.

---

## Task 1: Define OrchestratorUI Protocol

### Why It Matters
The codebase has three UI implementations (`TextualUI`, `NonInteractiveUI`, and `OrchestrationController`) that implement the same interface through copy-pasted method signatures. This violates DRY and makes interface changes error-prone. The Orchestrator uses `hasattr()` checks instead of proper typing, which:
- Provides no compile-time safety
- Prevents IDE autocomplete
- Makes adding new UI methods tedious (3+ places to update)

### What To Do

1. **Create Protocol in `src/debussy/ui/base.py`:**

```python
# Add to src/debussy/ui/base.py after line 29

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from debussy.core.models import Phase


class OrchestratorUI(Protocol):
    """Protocol defining the UI interface for orchestration.

    Implementations: TextualUI, NonInteractiveUI
    """

    @property
    def context(self) -> UIContext:
        """Return the UI context (single source of truth for state)."""
        ...

    def start(self, plan_name: str, total_phases: int) -> None:
        """Initialize the UI for a new orchestration run."""
        ...

    def stop(self) -> None:
        """Stop the UI (cleanup)."""
        ...

    def set_phase(self, phase: Phase, index: int) -> None:
        """Update the current phase being executed."""
        ...

    def set_state(self, state: UIState) -> None:
        """Update the UI state (running, paused, etc.)."""
        ...

    def log(self, message: str) -> None:
        """Log a message (respects verbose setting)."""
        ...

    def log_raw(self, message: str) -> None:
        """Log a message (ignores verbose setting)."""
        ...

    def get_pending_action(self) -> UserAction:
        """Get the next pending user action."""
        ...

    def toggle_verbose(self) -> bool:
        """Toggle verbose logging mode. Returns new state."""
        ...

    def show_status_popup(self, details: dict[str, str]) -> None:
        """Show detailed status information."""
        ...

    def confirm(self, message: str) -> bool:
        """Ask for user confirmation. Returns True if confirmed."""
        ...

    def update_token_stats(
        self,
        input_tokens: int,
        output_tokens: int,
        cost_usd: float,
        context_tokens: int,
        context_window: int = 200_000,
    ) -> None:
        """Update token usage statistics."""
        ...

    def set_active_agent(self, agent: str) -> None:
        """Update the active agent display."""
        ...

    def set_model(self, model: str) -> None:
        """Update the model name display."""
        ...
```

2. **Update `src/debussy/ui/__init__.py`:**

```python
# Add OrchestratorUI to exports
from debussy.ui.base import OrchestratorUI, UIContext, UIState, UserAction

__all__ = [
    "NonInteractiveUI",
    "OrchestratorUI",
    "OrchestrationController",
    "TextualUI",
    "UIContext",
    "UIState",
    "UserAction",
]
```

3. **Update Orchestrator type annotation in `src/debussy/core/orchestrator.py:70`:**

```python
# Change from:
self.ui: TextualUI | NonInteractiveUI = ...

# To:
from debussy.ui import OrchestratorUI
self.ui: OrchestratorUI = TextualUI() if self.config.interactive else NonInteractiveUI()
```

4. **Remove hasattr() checks in `src/debussy/core/orchestrator.py:82-96`:**

```python
# Change from:
def _on_token_stats(self, stats: TokenStats) -> None:
    if hasattr(self.ui, "update_token_stats"):
        self.ui.update_token_stats(...)

# To:
def _on_token_stats(self, stats: TokenStats) -> None:
    self.ui.update_token_stats(
        input_tokens=stats.input_tokens,
        output_tokens=stats.output_tokens,
        cost_usd=stats.cost_usd,
        context_tokens=stats.context_tokens,
        context_window=stats.context_window,
    )
```

Similarly for `_on_agent_change()` and `set_model()` calls.

### Acceptance Criteria
- [ ] Protocol defined in `ui/base.py`
- [ ] Pyright passes with no errors
- [ ] All `hasattr()` checks removed from orchestrator.py
- [ ] Both UI implementations satisfy the protocol (verified by type checker)
- [ ] Existing tests pass

### Priority: High
### Effort: Low
### Quick Win: Yes

---

## Task 2: Extract Docker/Path Utilities

### Why It Matters
There are two nearly-identical implementations of Docker command detection and Windows path conversion:

| Location | Function |
|----------|----------|
| `runners/claude.py:31-38` | `_get_docker_command()` |
| `cli.py:1229-1240` | `_get_docker_command()` |
| `runners/claude.py:75-91` | `_normalize_path_for_docker()` |
| `cli.py:1242-1254` | `_wsl_path()` |

Bug fixes must be applied in multiple places, and there are subtle differences (one uses `/mnt/` unconditionally, the other conditionally).

### What To Do

1. **Create `src/debussy/utils/__init__.py`:**

```python
"""Utility modules for Debussy."""
```

2. **Create `src/debussy/utils/docker.py`:**

```python
"""Docker-related utilities."""

from __future__ import annotations

import platform
import shutil
import subprocess
from pathlib import Path


def get_docker_command() -> list[str]:
    """Get the docker command prefix, using WSL on Windows if needed.

    Returns:
        Command list suitable for subprocess calls.
        On Windows without native Docker, returns ["wsl", "docker"].
    """
    if shutil.which("docker"):
        return ["docker"]
    # On Windows, try docker through WSL
    if platform.system() == "Windows" and shutil.which("wsl"):
        return ["wsl", "docker"]
    return ["docker"]  # Will fail, but gives clear error


def is_docker_available() -> bool:
    """Check if Docker is installed and the daemon is running."""
    docker_cmd = get_docker_command()
    # If using WSL, we don't need which() check
    if docker_cmd[0] != "wsl" and not shutil.which("docker"):
        return False
    try:
        result = subprocess.run(
            [*docker_cmd, "info"],
            capture_output=True,
            timeout=10,
            check=False,
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, OSError):
        return False


def normalize_path_for_docker(path: Path, use_wsl: bool = False) -> str:
    """Convert Windows path to Docker-compatible format.

    Args:
        path: Path to convert
        use_wsl: If True, use /mnt/c format (WSL). If False, use /c format (Docker Desktop).

    Returns:
        Path string suitable for Docker volume mounts.

    Examples:
        - Windows + use_wsl=False: C:\\Projects\\foo -> /c/Projects/foo
        - Windows + use_wsl=True:  C:\\Projects\\foo -> /mnt/c/Projects/foo
        - Unix: /home/user/foo -> /home/user/foo (unchanged)
    """
    if platform.system() == "Windows":
        path_str = str(path.resolve())
        if len(path_str) >= 2 and path_str[1] == ":":
            drive = path_str[0].lower()
            rest = path_str[2:].replace("\\", "/")
            if use_wsl:
                return f"/mnt/{drive}{rest}"
            return f"/{drive}{rest}"
    return str(path)


# Convenience alias for WSL path conversion
def wsl_path(path: Path) -> str:
    """Convert path to WSL format (/mnt/c/...).

    Convenience wrapper for normalize_path_for_docker(path, use_wsl=True).
    """
    return normalize_path_for_docker(path, use_wsl=True)
```

3. **Update imports in `src/debussy/runners/claude.py`:**

```python
# Remove local implementations (lines 31-91)
# Add import:
from debussy.utils.docker import (
    get_docker_command,
    is_docker_available,
    normalize_path_for_docker,
)

# Rename internal references:
# _get_docker_command -> get_docker_command
# _is_docker_available -> is_docker_available
# _normalize_path_for_docker -> normalize_path_for_docker
```

4. **Update imports in `src/debussy/cli.py`:**

```python
# Remove local implementations (lines 1229-1254)
# Add import:
from debussy.utils.docker import get_docker_command, wsl_path

# Update usage:
# _get_docker_command() -> get_docker_command()
# _wsl_path() -> wsl_path()
```

### Acceptance Criteria
- [ ] New `utils/docker.py` module created
- [ ] All duplicate functions removed from `runners/claude.py` and `cli.py`
- [ ] Imports updated in both files
- [ ] Existing tests pass
- [ ] `sandbox` CLI command still works

### Priority: High
### Effort: Low
### Quick Win: Yes

---

## Task 3: Add ClaudeRunner Callback Setter

### Why It Matters
The Orchestrator directly accesses ClaudeRunner's private attributes to set callbacks (line 74-77):

```python
self.claude._output_callback = self.ui.log
self.claude._token_stats_callback = self._on_token_stats
self.claude._agent_change_callback = self._on_agent_change
```

This violates encapsulation (underscore prefix indicates private) and couples the Orchestrator to ClaudeRunner's internal implementation.

### What To Do

1. **Add setter method in `src/debussy/runners/claude.py` after line 288:**

```python
def set_callbacks(
    self,
    output: Callable[[str], None] | None = None,
    token_stats: Callable[[TokenStats], None] | None = None,
    agent_change: Callable[[str], None] | None = None,
) -> None:
    """Configure runtime callbacks for UI integration.

    Args:
        output: Called with each line of Claude output
        token_stats: Called with token usage statistics
        agent_change: Called when active agent changes (Task tool)
    """
    if output is not None:
        self._output_callback = output
    if token_stats is not None:
        self._token_stats_callback = token_stats
    if agent_change is not None:
        self._agent_change_callback = agent_change
```

2. **Update Orchestrator in `src/debussy/core/orchestrator.py:72-77`:**

```python
# Change from:
self.claude._output_callback = self.ui.log
if self.config.interactive:
    self.claude._token_stats_callback = self._on_token_stats
    self.claude._agent_change_callback = self._on_agent_change

# To:
self.claude.set_callbacks(
    output=self.ui.log,
    token_stats=self._on_token_stats if self.config.interactive else None,
    agent_change=self._on_agent_change if self.config.interactive else None,
)
```

### Acceptance Criteria
- [ ] `set_callbacks()` method added to ClaudeRunner
- [ ] Orchestrator uses the new method
- [ ] No direct access to `_output_callback`, `_token_stats_callback`, `_agent_change_callback`
- [ ] Existing tests pass

### Priority: Medium
### Effort: Low
### Quick Win: Yes

---

## Task 4: Replace assert with RuntimeError

### Why It Matters
The code uses `assert` for runtime validation in `runners/claude.py:940-941`:

```python
assert process.stdout is not None
assert process.stderr is not None
```

Asserts are stripped when Python runs with optimization (`python -O`), which would cause cryptic `AttributeError` exceptions in production.

### What To Do

1. **Update `src/debussy/runners/claude.py:939-942`:**

```python
# Change from:
assert process.stdout is not None
assert process.stderr is not None

# To:
if process.stdout is None or process.stderr is None:
    raise RuntimeError(
        "Subprocess streams not initialized. "
        "This is a bug - please report it."
    )
```

2. **Review other assert usages in the codebase:**

```bash
grep -n "^assert " src/debussy/**/*.py
```

The `assert self.plan is not None` statements in orchestrator.py (lines 173, 305, 482) are acceptable because they follow `self.load_plan()` calls and document invariants for mypy. However, consider converting to explicit checks if they guard critical paths.

### Acceptance Criteria
- [ ] Subprocess stream asserts replaced with RuntimeError
- [ ] Code works correctly with `python -O`
- [ ] Error message is actionable

### Priority: Medium
### Effort: Low
### Quick Win: Yes

---

## Task 5: Refactor PIDRegistry Singleton

### Why It Matters
The `PIDRegistry` class uses `__new__` override for singleton pattern (lines 101-118), which:
- Makes testing difficult (global state persists between tests)
- Has potential thread-safety issues (no lock around instance creation)
- Is considered a Python anti-pattern

### What To Do

1. **Refactor `src/debussy/runners/claude.py:101-225`:**

```python
class PIDRegistry:
    """Registry of spawned Claude subprocess PIDs.

    This is a safety mechanism to ensure we can always clean up Claude
    processes, even on unexpected crashes or exits.

    Use get_pid_registry() to obtain the singleton instance.
    """

    def __init__(self) -> None:
        """Initialize the registry. Use get_pid_registry() instead."""
        self._pids: set[int] = set()
        self._atexit_registered: bool = False

    # ... rest of methods unchanged ...


# Module-level singleton management
_pid_registry: PIDRegistry | None = None


def get_pid_registry() -> PIDRegistry:
    """Get the global PID registry singleton.

    This is the preferred way to access the registry.
    """
    global _pid_registry
    if _pid_registry is None:
        _pid_registry = PIDRegistry()
    return _pid_registry


def reset_pid_registry() -> None:
    """Reset the global PID registry (for testing only).

    WARNING: Only call this in test fixtures, never in production code.
    """
    global _pid_registry
    if _pid_registry is not None:
        _pid_registry._pids.clear()
    _pid_registry = None


# Keep backwards-compatible alias (but prefer get_pid_registry())
pid_registry = get_pid_registry()
```

2. **Update tests to use `reset_pid_registry()` in fixtures.**

### Acceptance Criteria
- [ ] `__new__` override removed
- [ ] Factory function `get_pid_registry()` added
- [ ] `reset_pid_registry()` available for tests
- [ ] Backwards-compatible `pid_registry` alias preserved
- [ ] Existing tests pass

### Priority: Medium
### Effort: Low
### Quick Win: Yes

---

## Task 6: Extract ClaudeRunner Components

### Why It Matters
`ClaudeRunner` at 1,209 lines has 7+ distinct responsibilities making it the most complex class in the codebase (Maintainability Index: C). This makes it:
- Hard to test individual behaviors
- Risky to modify (changes to one responsibility can break others)
- Difficult to understand at a glance

### What To Do

This is a multi-step refactoring that should be done incrementally:

**Phase A: Extract JsonStreamParser**

Create `src/debussy/runners/stream_parser.py`:

```python
"""JSON stream parser for Claude CLI output."""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from typing import TextIO

from debussy.runners.claude import TokenStats


@dataclass
class StreamParserCallbacks:
    """Callbacks for stream parser events."""

    on_text: Callable[[str], None] | None = None
    on_tool_use: Callable[[dict], None] | None = None
    on_tool_result: Callable[[dict, str], None] | None = None
    on_token_stats: Callable[[TokenStats], None] | None = None
    on_agent_change: Callable[[str], None] | None = None


class JsonStreamParser:
    """Parses Claude's stream-json output format."""

    def __init__(
        self,
        callbacks: StreamParserCallbacks,
        jsonl_file: TextIO | None = None,
    ) -> None:
        self._callbacks = callbacks
        self._jsonl_file = jsonl_file
        self._current_agent = "Debussy"
        self._pending_task_ids: dict[str, str] = {}

    def parse_line(self, line: str) -> str | None:
        """Parse a single line of JSON stream output.

        Returns:
            Text content if this line contained assistant text, None otherwise.
        """
        # ... extract logic from _display_stream_event and related methods ...
```

**Phase B: Extract DockerCommandBuilder**

Create `src/debussy/runners/docker_builder.py`:

```python
"""Docker command building for sandboxed execution."""

from __future__ import annotations

import os
import shlex
from pathlib import Path

from debussy.utils.docker import get_docker_command, normalize_path_for_docker


class DockerCommandBuilder:
    """Builds Docker run commands for Claude execution."""

    def __init__(
        self,
        project_root: Path,
        sandbox_image: str,
        model: str,
    ) -> None:
        self._project_root = project_root
        self._sandbox_image = sandbox_image
        self._model = model

    def build_command(self, prompt: str) -> list[str]:
        """Build the full Docker command."""
        # ... extract from _build_claude_command sandbox branch ...
```

**Phase C: Slim down ClaudeRunner**

After extractions, ClaudeRunner should only:
- Coordinate subprocess lifecycle
- Delegate parsing to JsonStreamParser
- Delegate command building to DockerCommandBuilder

Target: Under 400 lines for ClaudeRunner core.

### Acceptance Criteria
- [ ] JsonStreamParser extracted with unit tests
- [ ] DockerCommandBuilder extracted with unit tests
- [ ] ClaudeRunner delegates to new components
- [ ] ClaudeRunner under 500 lines
- [ ] All existing integration tests pass
- [ ] Maintainability Index improves to B or better

### Priority: High
### Effort: High
### Quick Win: No

---

## Task 7: Add Constants Module

### Why It Matters
Magic numbers are scattered across the codebase without named constants:

| Value | Locations | Meaning |
|-------|-----------|---------|
| `200_000` | claude.py:239, base.py:51, controller.py:136 | Default Claude context window |
| `2 * 1024 * 1024` | claude.py:553 | Subprocess line buffer limit |
| `1800` | claude.py:253 | Default timeout seconds |

Named constants improve readability and ensure consistent values.

### What To Do

1. **Create `src/debussy/constants.py`:**

```python
"""Application-wide constants."""

# Claude API defaults
CLAUDE_DEFAULT_CONTEXT_WINDOW = 200_000
CLAUDE_DEFAULT_TIMEOUT_SECONDS = 1800

# Subprocess configuration
SUBPROCESS_LINE_BUFFER_BYTES = 2 * 1024 * 1024  # 2MB for large tool results

# Docker sandbox
SANDBOX_IMAGE_NAME = "debussy-sandbox:latest"
```

2. **Update imports across the codebase:**

```python
# runners/claude.py
from debussy.constants import (
    CLAUDE_DEFAULT_CONTEXT_WINDOW,
    CLAUDE_DEFAULT_TIMEOUT_SECONDS,
    SANDBOX_IMAGE_NAME,
    SUBPROCESS_LINE_BUFFER_BYTES,
)

# ui/base.py
from debussy.constants import CLAUDE_DEFAULT_CONTEXT_WINDOW
```

### Acceptance Criteria
- [ ] Constants module created
- [ ] All magic numbers replaced with named constants
- [ ] No hardcoded values remain for context window, timeout, or buffer size

### Priority: Low
### Effort: Low
### Quick Win: Yes

---

## Task 8: Consolidate Log Method Names

### Why It Matters
UI classes have inconsistent method naming for logging:

| TextualUI | NonInteractiveUI | Purpose |
|-----------|------------------|---------|
| `log()` | `log()` | Log with verbose check |
| `log_message()` | `log_message = log` | Alias |
| `log_raw()` | `log_raw()` | Log ignoring verbose |
| `log_message_raw()` | (missing) | Another alias |

This creates confusion about which method to call and violates DRY.

### What To Do

1. **Standardize on two methods in the Protocol:**
   - `log(message: str)` - Respects verbose setting
   - `log_raw(message: str)` - Always logs

2. **Remove aliases in implementations:**

In `src/debussy/ui/tui.py`, remove `log_message` and `log_message_raw` methods, keep only `log` and `log_raw`.

In `src/debussy/ui/interactive.py`, remove `log_message = log` alias.

3. **Update callers to use canonical names.**

### Acceptance Criteria
- [ ] Only `log()` and `log_raw()` in Protocol
- [ ] Aliases removed from implementations
- [ ] All callers use canonical method names
- [ ] Existing tests pass

### Priority: Low
### Effort: Low
### Quick Win: Yes

---

## Implementation Order

Recommended order based on dependencies and effort:

1. **Task 1: Define Protocol** - Unlocks type safety, no dependencies
2. **Task 2: Extract Docker Utils** - Simple DRY fix, no dependencies
3. **Task 4: Replace asserts** - Quick production safety fix
4. **Task 3: Callback setter** - Depends on nothing, improves encapsulation
5. **Task 5: PIDRegistry refactor** - Improves testability
6. **Task 7: Constants module** - Cosmetic, can be done anytime
7. **Task 8: Log method names** - Cosmetic, best done with Task 1
8. **Task 6: ClaudeRunner extraction** - Largest effort, do last

Tasks 1-5 can be done in a single focused session (estimated 2-3 hours total).
Task 6 should be its own dedicated sprint with thorough testing.

---

## Notes for Implementation

### Textual-Specific Considerations

The TUI architecture is sound:
- Message-based communication between controller and app is the correct pattern
- Reactive attributes on widgets are used appropriately
- Worker usage for orchestration is correct (runs in same event loop)

Do NOT refactor:
- The `OrchestrationController` posting messages to the app
- The reactive attributes on `HUDHeader` and `HotkeyBar`
- The `@work(exclusive=True)` pattern for orchestration

### Testing Strategy

After implementing the Protocol (Task 1), add a protocol compliance test:

```python
# tests/test_ui_protocol.py
from typing import get_type_hints
from debussy.ui import OrchestratorUI, TextualUI, NonInteractiveUI

def test_textual_ui_implements_protocol():
    """Verify TextualUI satisfies OrchestratorUI protocol."""
    # Get all methods from protocol
    protocol_methods = {
        name for name in dir(OrchestratorUI)
        if not name.startswith('_') and callable(getattr(OrchestratorUI, name, None))
    }

    # Verify TextualUI has all methods
    for method in protocol_methods:
        assert hasattr(TextualUI, method), f"TextualUI missing {method}"

def test_non_interactive_ui_implements_protocol():
    """Verify NonInteractiveUI satisfies OrchestratorUI protocol."""
    # Similar check for NonInteractiveUI
    ...
```

---

*Plan created by Textual TUI Expert based on CODE_REVIEW_REPORT.md analysis*
