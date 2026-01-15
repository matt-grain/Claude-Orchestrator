# Phase 5: ClaudeRunner Extraction Refactor

**Status:** Pending
**Master Plan:** [MASTER_PLAN.md](MASTER_PLAN.md)
**Depends On:** None (independent refactoring)
**Source:** [REFACTORING_PLAN.md](../../REFACTORING_PLAN.md) Task 6

---

## CRITICAL: Read These First

Before implementing ANYTHING, read these files to understand project patterns:

1. **Target file**: `src/debussy/runners/claude.py` - The 1,210 line god class to decompose
2. **Refactoring plan**: `docs/REFACTORING_PLAN.md` - Task 6 details
3. **Code review**: `docs/CODE_REVIEW_REPORT.md` - Original findings
4. **Existing utils**: `src/debussy/utils/docker.py` - Pattern for utility extraction
5. **Test patterns**: `tests/test_runners.py` - How runner tests are structured

**DO NOT** break existing functionality. This is a pure refactoring - behavior must be identical.

---

## Process Wrapper (MANDATORY)
- [ ] Read the files listed in "CRITICAL: Read These First" section
- [ ] **[IMPLEMENTATION - see Tasks below]**
- [ ] Pre-validation (ALL required):
  ```bash
  # Code quality - run from project root
  uv run ruff format . && uv run ruff check --fix .

  # Type checking
  uv run pyright src/debussy/

  # Tests - ALL tests must pass, not just new ones
  uv run pytest tests/ -x -v

  # Complexity check - ClaudeRunner should improve
  uv run radon cc src/debussy/runners/claude.py -a -s
  ```
- [ ] Fix loop: repeat pre-validation until ALL pass with 0 errors
- [ ] Write `notes/NOTES_phase3_templates_phase_5.md` with:
  - Summary of what was extracted
  - Lines of code before/after for each component
  - Maintainability Index changes
  - Any design decisions made
- [ ] Signal completion: `debussy done --phase 5`

## Gates (must pass before completion)

**ALL gates are BLOCKING. Do not signal completion until ALL pass.**

- ruff: 0 errors (command: `uv run ruff check .`)
- pyright: 0 errors in src/debussy/ (command: `uv run pyright src/debussy/`)
- tests: ALL tests pass (command: `uv run pytest tests/ -v`)
- complexity: ClaudeRunner class under 500 lines
- maintainability: radon MI grade B or better for claude.py

---

## Overview

Extract cohesive components from the 1,210-line ClaudeRunner god class to improve maintainability, testability, and code comprehension. The refactoring splits into three sub-phases:

- **5A**: Extract `JsonStreamParser` - Stream parsing logic (~280 lines)
- **5B**: Extract `DockerCommandBuilder` - Sandbox command construction (~120 lines)
- **5C**: Slim `ClaudeRunner` - Remove remaining duplication, final cleanup

## Dependencies
- Previous phase: None (independent refactoring task)
- Internal: Tasks 1-5 from REFACTORING_PLAN.md must be complete (they are)
- External: None

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Breaking stream parsing | Medium | High | Keep all existing tests passing |
| Missing edge cases | Medium | Medium | Add unit tests for extracted components |
| Callback wiring bugs | Low | High | Integration tests verify end-to-end |

---

## Tasks

### Sub-Phase 5A: Extract JsonStreamParser

The stream parsing logic is the largest cohesive unit (~280 lines). Extract it to handle JSON parsing separately from process management.

#### 5A.1: Create Stream Parser Module

- [ ] Create `src/debussy/runners/stream_parser.py` with:

```python
"""JSON stream parser for Claude CLI output."""

from __future__ import annotations

import json
import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import TextIO

logger = logging.getLogger(__name__)


@dataclass
class StreamParserCallbacks:
    """Callbacks for stream parser events."""

    on_text: Callable[[str], None] | None = None
    on_tool_use: Callable[[dict], None] | None = None
    on_tool_result: Callable[[dict, str], None] | None = None
    on_token_stats: Callable[..., None] | None = None  # TokenStats callback
    on_agent_change: Callable[[str], None] | None = None


class JsonStreamParser:
    """Parses Claude's stream-json output format.

    Handles:
    - Assistant text messages
    - Tool use events (Task, Bash, Read, Edit, etc.)
    - Tool results with subagent output extraction
    - Token statistics from usage events
    - Active agent tracking for Task tool
    """

    def __init__(
        self,
        callbacks: StreamParserCallbacks,
        jsonl_file: TextIO | None = None,
    ) -> None:
        """Initialize the parser.

        Args:
            callbacks: Event callbacks for parsed content
            jsonl_file: Optional file to write raw JSON lines
        """
        self._callbacks = callbacks
        self._jsonl_file = jsonl_file
        self._current_agent = "Debussy"
        self._pending_task_ids: dict[str, str] = {}  # tool_use_id -> agent_type
        self._needs_line_prefix = True
        self._full_text: list[str] = []

    def parse_line(self, line: str) -> str | None:
        """Parse a single line of JSON stream output.

        Returns:
            Text content if this line contained assistant text, None otherwise.
        """
        # Extract from ClaudeRunner._display_stream_event
        ...

    def get_full_text(self) -> str:
        """Get the accumulated full text from the stream."""
        return "".join(self._full_text)

    def reset(self) -> None:
        """Reset parser state for a new stream."""
        self._current_agent = "Debussy"
        self._pending_task_ids.clear()
        self._needs_line_prefix = True
        self._full_text.clear()

    # --- Private methods extracted from ClaudeRunner ---

    def _handle_content_block(self, event: dict) -> str | None:
        """Handle content_block_delta and content_block_stop events."""
        ...

    def _handle_message_event(self, event: dict) -> None:
        """Handle message_start and message_stop events."""
        ...

    def _handle_tool_use(self, content: dict) -> None:
        """Handle tool_use content blocks."""
        # Extract from _display_tool_use, _display_file_tool, _display_bash_tool, _display_task_tool
        ...

    def _handle_tool_result(self, content: dict, result_text: str) -> None:
        """Handle tool_result content blocks."""
        # Extract from _display_tool_result, _display_subagent_output, _display_subagent_output_str
        ...

    def _extract_token_stats(self, message: dict) -> None:
        """Extract token statistics from usage data."""
        # Extract from _handle_assistant_usage
        ...
```

#### 5A.2: Extract Methods from ClaudeRunner

- [ ] Move these methods to `JsonStreamParser`:
  - `_display_stream_event` (line 603) -> `parse_line` + `_handle_content_block`
  - `_handle_assistant_usage` (line 643) -> `_extract_token_stats`
  - `_handle_result_event` (line 663) -> integrate into `_handle_message_event`
  - `_display_tool_use` (line 689) -> `_handle_tool_use`
  - `_display_file_tool` (line 713) -> inline into `_handle_tool_use`
  - `_display_bash_tool` (line 719) -> inline into `_handle_tool_use`
  - `_display_task_tool` (line 726) -> `_handle_task_tool`
  - `_set_active_agent` (line 738) -> integrate into task handling
  - `_reset_active_agent` (line 743) -> integrate into task handling
  - `_display_tool_result` (line 758) -> `_handle_tool_result`
  - `_display_subagent_output` (line 785) -> `_format_subagent_list_output`
  - `_display_subagent_output_str` (line 810) -> `_format_subagent_str_output`

#### 5A.3: Update ClaudeRunner to Use Parser

- [ ] Add `JsonStreamParser` as a dependency:
  ```python
  from debussy.runners.stream_parser import JsonStreamParser, StreamParserCallbacks

  class ClaudeRunner:
      def __init__(self, ...):
          ...
          self._parser: JsonStreamParser | None = None

      def _create_parser(self) -> JsonStreamParser:
          """Create a configured stream parser."""
          return JsonStreamParser(
              callbacks=StreamParserCallbacks(
                  on_text=self._write_output,
                  on_tool_use=self._on_tool_use,
                  on_tool_result=self._on_tool_result,
                  on_token_stats=self._token_stats_callback,
                  on_agent_change=self._agent_change_callback,
              ),
              jsonl_file=self._jsonl_file,
          )
  ```

- [ ] Update `_stream_json_reader` to use the parser:
  ```python
  async def _stream_json_reader(self, stdout: asyncio.StreamReader, ...):
      self._parser = self._create_parser()
      async for line in stdout:
          text = self._parser.parse_line(line.decode())
          if text:
              full_text.append(text)
      return self._parser.get_full_text()
  ```

#### 5A.4: Write Unit Tests for Parser

- [ ] Create `tests/test_stream_parser.py`:
  ```python
  import pytest
  from debussy.runners.stream_parser import JsonStreamParser, StreamParserCallbacks

  class TestJsonStreamParser:
      def test_parses_assistant_text(self):
          """Parser extracts text from content_block_delta events."""

      def test_tracks_task_tool_agent(self):
          """Parser tracks active agent from Task tool calls."""

      def test_extracts_token_stats(self):
          """Parser extracts token usage from message events."""

      def test_handles_subagent_output_list(self):
          """Parser formats list-style subagent output."""

      def test_handles_subagent_output_string(self):
          """Parser formats string-style subagent output."""

      def test_writes_to_jsonl_file(self):
          """Parser writes raw JSON to optional file."""
  ```

---

### Sub-Phase 5B: Extract DockerCommandBuilder

The Docker/sandbox command construction is self-contained (~120 lines).

#### 5B.1: Create Docker Builder Module

- [ ] Create `src/debussy/runners/docker_builder.py`:

```python
"""Docker command building for sandboxed Claude execution."""

from __future__ import annotations

import os
import platform
import shlex
from pathlib import Path

from debussy.utils.docker import get_docker_command, normalize_path_for_docker

# Default sandbox image
SANDBOX_IMAGE = "debussy-sandbox:latest"


class DockerCommandBuilder:
    """Builds Docker run commands for sandboxed Claude execution.

    Handles:
    - Volume mounts for project and Claude config
    - Windows path normalization
    - WSL wrapper for Windows without native Docker
    - Environment variable passthrough
    """

    def __init__(
        self,
        project_root: Path,
        model: str,
        sandbox_image: str = SANDBOX_IMAGE,
    ) -> None:
        """Initialize the builder.

        Args:
            project_root: Root directory of the project to mount
            model: Claude model name (e.g., "opus", "sonnet")
            sandbox_image: Docker image name for sandbox
        """
        self._project_root = project_root
        self._model = model
        self._sandbox_image = sandbox_image
        self._use_wsl = self._should_use_wsl()

    def _should_use_wsl(self) -> bool:
        """Check if we need to use WSL for Docker."""
        docker_cmd = get_docker_command()
        return docker_cmd[0] == "wsl"

    def build_command(self, prompt: str, timeout: int = 1800) -> list[str]:
        """Build the complete Docker run command.

        Args:
            prompt: The prompt to send to Claude
            timeout: Timeout in seconds

        Returns:
            Command list for subprocess execution.
        """
        ...

    def _build_volume_mounts(self) -> list[str]:
        """Build volume mount arguments."""
        # Extract from _build_claude_command sandbox branch
        ...

    def _build_env_vars(self) -> list[str]:
        """Build environment variable arguments."""
        ...

    def _build_claude_args(self, prompt: str, timeout: int) -> list[str]:
        """Build the Claude CLI arguments."""
        ...
```

#### 5B.2: Extract from ClaudeRunner

- [ ] Move sandbox-related code from `_build_claude_command` (lines 448-536):
  - Volume mount construction
  - Path normalization calls
  - WSL wrapper logic
  - Shadow mount logic for .venv/.git/__pycache__
  - Claude command arguments

- [ ] Keep in ClaudeRunner:
  - Non-sandbox command building (simple case)
  - Decision logic for sandbox vs non-sandbox
  - `validate_sandbox_mode()` method

#### 5B.3: Update ClaudeRunner

- [ ] Use `DockerCommandBuilder` in `_build_claude_command`:
  ```python
  from debussy.runners.docker_builder import DockerCommandBuilder

  def _build_claude_command(self, prompt: str) -> list[str]:
      if self.config.sandbox_mode == "devcontainer":
          builder = DockerCommandBuilder(
              project_root=self.project_root,
              model=self.config.model,
          )
          return builder.build_command(prompt, self.config.timeout)

      # Non-sandbox path (keep inline - simple)
      return [
          "claude",
          "--output-format", "stream-json",
          "--model", self.config.model,
          ...
      ]
  ```

#### 5B.4: Write Unit Tests

- [ ] Create `tests/test_docker_builder.py`:
  ```python
  import pytest
  from pathlib import Path
  from debussy.runners.docker_builder import DockerCommandBuilder

  class TestDockerCommandBuilder:
      def test_builds_volume_mounts(self):
          """Builder creates correct volume mount arguments."""

      def test_normalizes_windows_paths(self):
          """Builder normalizes Windows paths for Docker."""

      def test_uses_wsl_wrapper_when_needed(self):
          """Builder wraps command in WSL on Windows without native Docker."""

      def test_passes_environment_variables(self):
          """Builder passes required env vars to container."""

      def test_includes_shadow_mounts(self):
          """Builder adds tmpfs mounts for .venv/.git/__pycache__."""
  ```

---

### Sub-Phase 5C: Final Cleanup

After extractions, clean up ClaudeRunner and verify improvements.

#### 5C.1: Remove Dead Code

- [ ] Remove any methods that were fully extracted
- [ ] Remove unused imports
- [ ] Consolidate remaining private methods

#### 5C.2: Add Module Exports

- [ ] Update `src/debussy/runners/__init__.py`:
  ```python
  from debussy.runners.claude import ClaudeRunner, TokenStats, get_pid_registry
  from debussy.runners.stream_parser import JsonStreamParser, StreamParserCallbacks
  from debussy.runners.docker_builder import DockerCommandBuilder

  __all__ = [
      "ClaudeRunner",
      "DockerCommandBuilder",
      "JsonStreamParser",
      "StreamParserCallbacks",
      "TokenStats",
      "get_pid_registry",
  ]
  ```

#### 5C.3: Verify Metrics

- [ ] Run complexity analysis:
  ```bash
  uv run radon cc src/debussy/runners/claude.py -a -s
  uv run radon mi src/debussy/runners/ -s
  ```

- [ ] Document improvements in notes:
  | Metric | Before | After |
  |--------|--------|-------|
  | ClaudeRunner lines | 1,210 | <500 |
  | Maintainability Index | C (8.07) | B+ |
  | Max cyclomatic complexity | ? | <10 |

#### 5C.4: Integration Testing

- [ ] Run full test suite: `uv run pytest tests/ -v`
- [ ] Manual test with real plan:
  ```bash
  # Test non-sandbox mode
  debussy run docs/plans/phase3-templates/MASTER_PLAN.md --phase 1

  # Test sandbox mode (if Docker available)
  debussy run docs/plans/phase3-templates/MASTER_PLAN.md --phase 1 --sandbox
  ```

---

## Files to Create/Modify

| File | Action | Purpose |
|------|--------|---------|
| `src/debussy/runners/stream_parser.py` | Create | JSON stream parsing |
| `src/debussy/runners/docker_builder.py` | Create | Docker command construction |
| `src/debussy/runners/claude.py` | Modify | Slim down, delegate to new components |
| `src/debussy/runners/__init__.py` | Modify | Export new classes |
| `tests/test_stream_parser.py` | Create | Parser unit tests |
| `tests/test_docker_builder.py` | Create | Builder unit tests |

## Patterns to Follow

**MANDATORY: Follow these patterns from existing code.**

| Pattern | Reference File | What to Copy |
|---------|----------------|--------------|
| Dataclass callbacks | `src/debussy/core/models.py` | Use `@dataclass` for config objects |
| Utility extraction | `src/debussy/utils/docker.py` | Module-level functions + classes |
| Test structure | `tests/test_runners.py` | Fixtures, parametrized tests |
| Type hints | `src/debussy/runners/claude.py` | Full type annotations |

## Test Strategy

**Tests are NOT optional. Each extraction MUST maintain test coverage.**

- [ ] Parser unit tests cover all event types
- [ ] Builder unit tests cover Windows/Unix paths
- [ ] Existing `test_runners.py` tests still pass
- [ ] Integration test: end-to-end phase execution
- [ ] Coverage does not decrease (currently ~60%)

## Acceptance Criteria

**ALL criteria must be met before signaling completion:**

- [ ] `ClaudeRunner` class is under 500 lines
- [ ] `JsonStreamParser` extracted with unit tests
- [ ] `DockerCommandBuilder` extracted with unit tests
- [ ] All 356+ existing tests pass
- [ ] Radon maintainability index B or better
- [ ] No regression in functionality
- [ ] `uv run ruff check .` returns 0 errors
- [ ] `uv run pyright src/debussy/` returns 0 errors

## Rollback Plan

- Each sub-phase is a separate commit
- If issues found, revert to previous sub-phase commit
- Extracted classes can be inlined back if needed
- Feature flags not needed (pure refactoring)

---

## Implementation Notes

### Callback Wiring

The trickiest part is maintaining the callback chain:

```
ClaudeRunner
    └── _output_callback (set by Orchestrator)
    └── _token_stats_callback (set by Orchestrator)
    └── _agent_change_callback (set by Orchestrator)
            │
            ▼
    JsonStreamParser
        └── callbacks.on_text → _output_callback
        └── callbacks.on_token_stats → _token_stats_callback
        └── callbacks.on_agent_change → _agent_change_callback
```

The parser should NOT know about the Orchestrator. It receives callbacks and calls them.

### State Management

The parser maintains state that must be reset between phases:
- `_current_agent` - Reset to "Debussy" at phase start
- `_pending_task_ids` - Clear at phase start
- `_needs_line_prefix` - Reset for new output

ClaudeRunner should call `parser.reset()` at the start of each `execute_phase()`.

### Testing Without Docker

For `DockerCommandBuilder` tests, mock the `get_docker_command()` function:

```python
@pytest.fixture
def mock_native_docker(monkeypatch):
    monkeypatch.setattr(
        "debussy.runners.docker_builder.get_docker_command",
        lambda: ["docker"]
    )

@pytest.fixture
def mock_wsl_docker(monkeypatch):
    monkeypatch.setattr(
        "debussy.runners.docker_builder.get_docker_command",
        lambda: ["wsl", "docker"]
    )
```
