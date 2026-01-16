# Phase 6: Context Monitoring & Smart Restart

**Status:** Pending
**Master Plan:** [MASTER_PLAN.md](MASTER_PLAN.md)
**Depends On:** None (can run independently)
**Origin:** Discussion with Matt on session context limits and restart strategies

---

## CRITICAL: Read These First

Before implementing ANYTHING, read these files to understand project patterns:

1. **FUTURE.md**: `docs/FUTURE.md` - Token reporting bug context (why we can't trust stream-json tokens)
2. **ClaudeRunner**: `src/debussy/runners/claude.py` - Current stream parsing, where monitoring hooks will go
3. **Orchestrator**: `src/debussy/orchestrator.py` - Phase lifecycle, where restart logic lives
4. **State Manager**: `src/debussy/core/state.py` - How to persist checkpoint data
5. **Progress Skill**: `src/debussy/skills/debussy_progress.py` - Existing progress reporting mechanism

**DO NOT** break existing phase execution. Changes should be additive with sensible defaults.

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
  ```
- [ ] Fix loop: repeat pre-validation until ALL pass with 0 errors
- [ ] Write `notes/NOTES_phase3_templates_phase_6.md` with:
  - Summary of what was implemented
  - Configuration options added
  - Design decisions and trade-offs
  - Example restart scenarios tested
- [ ] Signal completion: `debussy done --phase 6`

## Gates (must pass before completion)

**ALL gates are BLOCKING. Do not signal completion until ALL pass.**

- ruff: 0 errors (command: `uv run ruff check .`)
- pyright: 0 errors in src/debussy/ (command: `uv run pyright src/debussy/`)
- tests: ALL tests pass (command: `uv run pytest tests/ -v`)
- coverage: No decrease from current (~60%)

---

## Overview

Implement context monitoring for long-running phases to prevent quality degradation from auto-compaction. When estimated context usage exceeds a threshold, Debussy gracefully restarts the phase with injected context about prior progress.

**Problem Statement:**
- Claude Code's auto-compaction degrades quality for complex tasks
- `stream-json` token counts are cumulative (useless for current context)
- Long phases can hit context limits mid-task, losing coherence

**Solution:**
1. Estimate context usage via token counting + tool call heuristics
2. Capture progress checkpoints during execution
3. Auto-commit at phase boundaries for clean git diffs
4. On threshold breach, restart phase with progress context injected

## Dependencies
- Previous phase: None (independent feature)
- Internal: Uses existing StateManager, progress skill infrastructure
- External: `tiktoken` package for token estimation (optional, can use heuristics)

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Estimation inaccuracy | Medium | Low | Conservative threshold (80%), fallback to tool count |
| Restart loops | Low | High | Max restart count (3), exponential backoff |
| Progress not captured | Medium | Medium | Git diff as fallback, warn if no /debussy-progress calls |
| Lost work on restart | Low | Medium | Auto-commit before restart, clear warning in logs |

---

## Tasks

### Sub-Phase 6A: Context Estimation

Build the context usage estimator that doesn't rely on broken stream-json tokens.

#### 6A.1: Create Context Estimator Module

- [ ] Create `src/debussy/runners/context_estimator.py`:

```python
"""Context usage estimation for Claude sessions.

Since stream-json reports cumulative tokens (not current context),
we estimate context growth from observable signals:
- File content read (we know the sizes)
- Tool output sizes
- Prompt sizes we inject
- Heuristic for Claude's reasoning overhead
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)

# Claude's context window size (200k for opus/sonnet)
DEFAULT_CONTEXT_LIMIT = 200_000

# Rough chars-to-tokens ratio (conservative)
CHARS_TO_TOKENS_RATIO = 4

# Overhead multiplier for Claude's reasoning (CoT, tool formatting)
REASONING_OVERHEAD = 1.3


@dataclass
class ContextEstimate:
    """Current context usage estimate."""

    file_tokens: int = 0  # From Read tool outputs
    tool_output_tokens: int = 0  # Other tool results
    prompt_tokens: int = 0  # Our injected prompts
    tool_call_count: int = 0  # Heuristic fallback

    @property
    def total_estimated(self) -> int:
        """Total estimated tokens with reasoning overhead."""
        base = self.file_tokens + self.tool_output_tokens + self.prompt_tokens
        return int(base * REASONING_OVERHEAD)

    @property
    def usage_percentage(self, limit: int = DEFAULT_CONTEXT_LIMIT) -> float:
        """Estimated percentage of context used."""
        return (self.total_estimated / limit) * 100


class ContextEstimator:
    """Estimates context window usage from observable events.

    Usage:
        estimator = ContextEstimator(threshold_percent=80)

        # During stream processing
        estimator.add_file_read(path, content)
        estimator.add_tool_output(tool_name, output)
        estimator.add_prompt(prompt_text)

        if estimator.should_restart():
            # Trigger phase restart
    """

    def __init__(
        self,
        threshold_percent: float = 80.0,
        context_limit: int = DEFAULT_CONTEXT_LIMIT,
        tool_call_threshold: int = 100,  # Fallback heuristic
    ) -> None:
        self._threshold = threshold_percent
        self._context_limit = context_limit
        self._tool_call_threshold = tool_call_threshold
        self._estimate = ContextEstimate()

    def add_file_read(self, path: Path | str, content: str) -> None:
        """Track tokens from a file read."""
        tokens = self._estimate_tokens(content)
        self._estimate.file_tokens += tokens
        logger.debug(f"File read: {path} ({tokens} tokens)")

    def add_tool_output(self, tool_name: str, output: str) -> None:
        """Track tokens from tool output."""
        tokens = self._estimate_tokens(output)
        self._estimate.tool_output_tokens += tokens
        self._estimate.tool_call_count += 1
        logger.debug(f"Tool {tool_name}: {tokens} tokens (call #{self._estimate.tool_call_count})")

    def add_prompt(self, prompt: str) -> None:
        """Track tokens from injected prompts."""
        tokens = self._estimate_tokens(prompt)
        self._estimate.prompt_tokens += tokens

    def should_restart(self) -> bool:
        """Check if context usage warrants a restart."""
        # Primary check: estimated token percentage
        if self._estimate.usage_percentage >= self._threshold:
            logger.warning(
                f"Context threshold reached: {self._estimate.usage_percentage:.1f}% "
                f"(~{self._estimate.total_estimated} tokens)"
            )
            return True

        # Fallback check: tool call count (safety net)
        if self._estimate.tool_call_count >= self._tool_call_threshold:
            logger.warning(
                f"Tool call threshold reached: {self._estimate.tool_call_count} calls"
            )
            return True

        return False

    def get_estimate(self) -> ContextEstimate:
        """Get current context estimate."""
        return self._estimate

    def reset(self) -> None:
        """Reset estimator for new session."""
        self._estimate = ContextEstimate()

    @staticmethod
    def _estimate_tokens(text: str) -> int:
        """Estimate token count from text.

        Uses simple char ratio. Could optionally use tiktoken for accuracy.
        """
        return len(text) // CHARS_TO_TOKENS_RATIO
```

#### 6A.2: Integrate Estimator into ClaudeRunner

- [ ] Add estimator to ClaudeRunner initialization:
  ```python
  from debussy.runners.context_estimator import ContextEstimator

  class ClaudeRunner:
      def __init__(self, ...):
          ...
          self._context_estimator: ContextEstimator | None = None
          self._restart_callback: Callable[[], None] | None = None
  ```

- [ ] Hook estimator into stream parsing (in `_handle_tool_result` or parser):
  ```python
  # When Read tool result received
  if tool_name == "Read":
      self._context_estimator.add_file_read(path, content)
  else:
      self._context_estimator.add_tool_output(tool_name, output_text)

  if self._context_estimator.should_restart():
      self._restart_callback()
  ```

#### 6A.3: Write Unit Tests

- [ ] Create `tests/test_context_estimator.py`:
  ```python
  import pytest
  from debussy.runners.context_estimator import ContextEstimator, ContextEstimate

  class TestContextEstimator:
      def test_estimates_file_tokens(self):
          """Estimator counts tokens from file reads."""
          estimator = ContextEstimator()
          estimator.add_file_read("test.py", "x" * 4000)  # ~1000 tokens
          assert estimator.get_estimate().file_tokens == 1000

      def test_triggers_restart_at_threshold(self):
          """Estimator triggers restart when threshold exceeded."""
          estimator = ContextEstimator(threshold_percent=80, context_limit=1000)
          estimator.add_tool_output("Read", "x" * 3200)  # 800 tokens = 80%
          assert estimator.should_restart()

      def test_tool_call_fallback(self):
          """Estimator triggers restart after too many tool calls."""
          estimator = ContextEstimator(tool_call_threshold=50)
          for i in range(50):
              estimator.add_tool_output("Bash", "ok")
          assert estimator.should_restart()

      def test_reset_clears_state(self):
          """Reset clears all accumulated estimates."""
          estimator = ContextEstimator()
          estimator.add_file_read("test.py", "content")
          estimator.reset()
          assert estimator.get_estimate().total_estimated == 0
  ```

---

### Sub-Phase 6B: Progress Checkpoint Capture

Capture progress during execution so restarts can continue from where they left off.

#### 6B.1: Create Checkpoint Manager

- [ ] Create `src/debussy/core/checkpoint.py`:

```python
"""Phase checkpoint management for smart restarts.

Captures progress signals during phase execution:
- /debussy-progress skill calls
- Git diff of modified files
- Task tool completions

Used to inject context when restarting a phase mid-execution.
"""

from __future__ import annotations

import subprocess
import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class ProgressEntry:
    """Single progress log entry."""
    timestamp: datetime
    message: str
    phase_id: str


@dataclass
class PhaseCheckpoint:
    """Checkpoint state for a phase execution."""

    phase_id: str
    phase_name: str
    start_commit: str | None = None  # Git HEAD when phase started
    progress_entries: list[ProgressEntry] = field(default_factory=list)
    modified_files: list[str] = field(default_factory=list)
    restart_count: int = 0

    def add_progress(self, message: str) -> None:
        """Record a progress entry from /debussy-progress."""
        self.progress_entries.append(ProgressEntry(
            timestamp=datetime.now(),
            message=message,
            phase_id=self.phase_id,
        ))

    def capture_git_state(self, project_root: Path) -> None:
        """Capture current git state (modified files, diff stats)."""
        try:
            # Get list of modified files
            result = subprocess.run(
                ["git", "diff", "--name-only"],
                cwd=project_root,
                capture_output=True,
                text=True,
            )
            if result.returncode == 0:
                self.modified_files = [
                    f for f in result.stdout.strip().split("\n") if f
                ]
        except Exception as e:
            logger.warning(f"Failed to capture git state: {e}")

    def format_restart_context(self) -> str:
        """Format checkpoint as context for restart prompt."""
        lines = [
            "⚠️ SESSION RESET: Context limit reached, fresh session started.",
            f"Phase: {self.phase_id} - {self.phase_name}",
            f"Restart attempt: {self.restart_count + 1}",
            "",
        ]

        if self.progress_entries:
            lines.append("Progress logged before reset:")
            for entry in self.progress_entries:
                lines.append(f"  ✓ {entry.message}")
            lines.append("")

        if self.modified_files:
            lines.append("Files modified (do not recreate):")
            for f in self.modified_files[:20]:  # Limit to 20 files
                lines.append(f"  - {f}")
            if len(self.modified_files) > 20:
                lines.append(f"  ... and {len(self.modified_files) - 20} more")
            lines.append("")

        lines.extend([
            "IMPORTANT:",
            "- Continue from where you stopped",
            "- Do NOT redo completed work",
            "- Review modified files to understand current state",
            "- Use /debussy-progress to log significant progress",
        ])

        return "\n".join(lines)


class CheckpointManager:
    """Manages phase checkpoints across restarts."""

    def __init__(self, project_root: Path) -> None:
        self._project_root = project_root
        self._current: PhaseCheckpoint | None = None

    def start_phase(self, phase_id: str, phase_name: str) -> PhaseCheckpoint:
        """Start tracking a new phase."""
        # Capture starting git state
        start_commit = self._get_head_commit()

        self._current = PhaseCheckpoint(
            phase_id=phase_id,
            phase_name=phase_name,
            start_commit=start_commit,
        )
        return self._current

    def get_current(self) -> PhaseCheckpoint | None:
        """Get current phase checkpoint."""
        return self._current

    def record_progress(self, message: str) -> None:
        """Record progress from /debussy-progress skill."""
        if self._current:
            self._current.add_progress(message)

    def prepare_restart(self) -> str:
        """Prepare checkpoint context for restart."""
        if not self._current:
            return ""

        # Capture git state before restart
        self._current.capture_git_state(self._project_root)
        self._current.restart_count += 1

        return self._current.format_restart_context()

    def _get_head_commit(self) -> str | None:
        """Get current HEAD commit hash."""
        try:
            result = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=self._project_root,
                capture_output=True,
                text=True,
            )
            if result.returncode == 0:
                return result.stdout.strip()
        except Exception:
            pass
        return None
```

#### 6B.2: Hook Progress Skill to Checkpoint Manager

- [ ] Update orchestrator to pass progress to checkpoint manager:
  ```python
  # In Orchestrator, when /debussy-progress is detected in output
  def _handle_progress_skill(self, message: str) -> None:
      self._checkpoint_manager.record_progress(message)
  ```

- [ ] Parse stream for progress skill invocations (look for Skill tool with skill="debussy-progress")

#### 6B.3: Write Unit Tests

- [ ] Create `tests/test_checkpoint.py`:
  ```python
  import pytest
  from pathlib import Path
  from debussy.core.checkpoint import CheckpointManager, PhaseCheckpoint

  class TestPhaseCheckpoint:
      def test_formats_restart_context(self):
          """Checkpoint formats readable restart context."""
          cp = PhaseCheckpoint(phase_id="1", phase_name="Setup")
          cp.add_progress("Created project structure")
          cp.add_progress("Installed dependencies")
          cp.modified_files = ["src/main.py", "pyproject.toml"]

          context = cp.format_restart_context()
          assert "SESSION RESET" in context
          assert "Created project structure" in context
          assert "src/main.py" in context

      def test_restart_count_increments(self):
          """Restart count tracks attempts."""
          cp = PhaseCheckpoint(phase_id="1", phase_name="Setup")
          assert cp.restart_count == 0
          cp.restart_count += 1
          assert "Restart attempt: 2" in cp.format_restart_context()

  class TestCheckpointManager:
      def test_start_phase_captures_commit(self, tmp_path, monkeypatch):
          """Starting phase captures current HEAD."""
          # ... mock git commands

      def test_prepare_restart_captures_diff(self, tmp_path):
          """Preparing restart captures modified files."""
          # ... test git diff capture
  ```

---

### Sub-Phase 6C: Auto-Commit at Phase Boundaries

Automatically commit at phase end for clean checkpoints.

#### 6C.1: Add Auto-Commit Configuration

- [ ] Update `src/debussy/config.py`:
  ```python
  @dataclass
  class DebussyConfig:
      ...
      auto_commit: bool = True
      commit_on_failure: bool = False
      commit_message_template: str = "Debussy: Phase {phase_id} - {phase_name} {status}"
  ```

#### 6C.2: Implement Auto-Commit Logic

- [ ] Add to `src/debussy/orchestrator.py`:
  ```python
  def _auto_commit_phase(self, phase_id: str, phase_name: str, success: bool) -> bool:
      """Auto-commit changes after phase completion.

      Returns True if commit was made, False otherwise.
      """
      if not self.config.auto_commit:
          return False

      if not success and not self.config.commit_on_failure:
          logger.info("Skipping auto-commit for failed phase")
          return False

      # Check if there are changes to commit
      result = subprocess.run(
          ["git", "status", "--porcelain"],
          cwd=self.project_root,
          capture_output=True,
          text=True,
      )

      if not result.stdout.strip():
          logger.info("No changes to commit")
          return False

      # Check for uncommitted changes warning
      status = "✓" if success else "⚠️ partial"
      message = self.config.commit_message_template.format(
          phase_id=phase_id,
          phase_name=phase_name,
          status=status,
      )

      # Stage and commit with proper attribution
      subprocess.run(["git", "add", "-A"], cwd=self.project_root)

      # Use heredoc-style commit for proper formatting
      full_message = f"{message}\n\nCo-Authored-By: Claude <{self.config.model}@anthropic.com>"
      subprocess.run(
          ["git", "commit", "-m", full_message],
          cwd=self.project_root,
      )

      logger.info(f"Auto-committed: {message}")
      return True
  ```

#### 6C.3: Add CLI Flags

- [ ] Update `src/debussy/cli.py` run command:
  ```python
  @click.option("--auto-commit/--no-auto-commit", default=None,
                help="Auto-commit after each phase (default: from config)")
  @click.option("--allow-dirty", is_flag=True,
                help="Allow starting with uncommitted changes")
  ```

#### 6C.4: Handle Edge Cases

- [ ] Check for dirty working directory at start:
  ```python
  def _check_clean_working_directory(self) -> bool:
      """Warn if there are uncommitted changes before starting."""
      result = subprocess.run(
          ["git", "status", "--porcelain"],
          cwd=self.project_root,
          capture_output=True,
          text=True,
      )

      if result.stdout.strip():
          uncommitted = len(result.stdout.strip().split("\n"))
          logger.warning(
              f"Working directory has {uncommitted} uncommitted changes. "
              "Use --allow-dirty to proceed or commit/stash first."
          )
          return False
      return True
  ```

#### 6C.5: Write Unit Tests

- [ ] Add tests to `tests/test_orchestrator.py`:
  ```python
  class TestAutoCommit:
      def test_commits_on_success(self, orchestrator_with_git):
          """Auto-commits after successful phase."""

      def test_skips_commit_on_failure(self, orchestrator_with_git):
          """Skips commit on failure unless configured."""

      def test_respects_no_auto_commit_flag(self, orchestrator_with_git):
          """Respects --no-auto-commit flag."""

      def test_warns_on_dirty_directory(self, orchestrator_with_git):
          """Warns when starting with uncommitted changes."""
  ```

---

### Sub-Phase 6D: Smart Restart Logic

Tie it all together: detect threshold, capture checkpoint, restart with context.

#### 6D.1: Implement Restart Orchestration

- [ ] Add restart logic to `src/debussy/orchestrator.py`:
  ```python
  MAX_RESTARTS = 3

  async def _execute_phase_with_restart(
      self,
      phase: Phase,
      prompt: str,
  ) -> PhaseResult:
      """Execute phase with automatic restart on context overflow."""

      restart_count = 0

      while restart_count <= MAX_RESTARTS:
          # Start/continue checkpoint tracking
          checkpoint = self._checkpoint_manager.start_phase(
              phase.id, phase.name
          ) if restart_count == 0 else self._checkpoint_manager.get_current()

          # Prepare prompt with restart context if applicable
          effective_prompt = prompt
          if restart_count > 0:
              restart_context = self._checkpoint_manager.prepare_restart()
              effective_prompt = f"{restart_context}\n\n---\n\n{prompt}"

          # Create estimator for this attempt
          estimator = ContextEstimator(
              threshold_percent=self.config.context_threshold,
              tool_call_threshold=self.config.tool_call_threshold,
          )

          # Execute with restart callback
          should_restart = False

          def on_context_limit():
              nonlocal should_restart
              should_restart = True
              # Signal runner to gracefully stop
              self._runner.request_stop()

          self._runner.set_context_estimator(estimator)
          self._runner.set_restart_callback(on_context_limit)

          result = await self._runner.execute_phase(
              phase=phase,
              prompt=effective_prompt,
          )

          if not should_restart:
              # Normal completion
              return result

          # Context limit hit - restart
          restart_count += 1
          logger.warning(
              f"Phase {phase.id} restarting ({restart_count}/{MAX_RESTARTS}) "
              f"due to context limit"
          )

          if restart_count > MAX_RESTARTS:
              logger.error(f"Max restarts exceeded for phase {phase.id}")
              return PhaseResult(
                  success=False,
                  error="Max restart attempts exceeded",
              )

      return result
  ```

#### 6D.2: Add Configuration Options

- [ ] Update config with new options:
  ```python
  @dataclass
  class DebussyConfig:
      ...
      # Context monitoring
      context_threshold: float = 80.0  # Percentage to trigger restart
      tool_call_threshold: int = 100  # Fallback heuristic
      max_restarts: int = 3  # Max restart attempts per phase

      # Auto-commit
      auto_commit: bool = True
      commit_on_failure: bool = False
  ```

#### 6D.3: Update CLI with New Options

- [ ] Add flags to run command:
  ```python
  @click.option("--context-threshold", type=float, default=None,
                help="Context usage % to trigger restart (default: 80)")
  @click.option("--max-restarts", type=int, default=None,
                help="Max restart attempts per phase (default: 3)")
  ```

#### 6D.4: Write Integration Tests

- [ ] Create `tests/test_smart_restart.py`:
  ```python
  import pytest
  from unittest.mock import AsyncMock, MagicMock

  class TestSmartRestart:
      @pytest.mark.asyncio
      async def test_restarts_on_context_threshold(self):
          """Orchestrator restarts phase when context threshold hit."""

      @pytest.mark.asyncio
      async def test_injects_checkpoint_context(self):
          """Restart prompt includes checkpoint context."""

      @pytest.mark.asyncio
      async def test_respects_max_restarts(self):
          """Fails after max restart attempts."""

      @pytest.mark.asyncio
      async def test_captures_progress_entries(self):
          """Progress from /debussy-progress appears in restart context."""

      @pytest.mark.asyncio
      async def test_captures_git_diff(self):
          """Modified files appear in restart context."""
  ```

---

## Files to Create/Modify

| File | Action | Purpose |
|------|--------|---------|
| `src/debussy/runners/context_estimator.py` | Create | Context usage estimation |
| `src/debussy/core/checkpoint.py` | Create | Phase checkpoint management |
| `src/debussy/runners/claude.py` | Modify | Hook estimator into stream processing |
| `src/debussy/orchestrator.py` | Modify | Restart logic, auto-commit |
| `src/debussy/config.py` | Modify | New config options |
| `src/debussy/cli.py` | Modify | New CLI flags |
| `tests/test_context_estimator.py` | Create | Estimator tests |
| `tests/test_checkpoint.py` | Create | Checkpoint tests |
| `tests/test_smart_restart.py` | Create | Integration tests |

## Patterns to Follow

**MANDATORY: Follow these patterns from existing code.**

| Pattern | Reference File | What to Copy |
|---------|----------------|--------------|
| Dataclass models | `src/debussy/core/models.py` | Use `@dataclass` for state objects |
| Config loading | `src/debussy/config.py` | YAML-based config with defaults |
| CLI options | `src/debussy/cli.py` | Click decorators, config override pattern |
| Subprocess calls | `src/debussy/core/compliance.py` | Safe git/subprocess patterns |
| Test fixtures | `tests/conftest.py` | Pytest fixtures, mocking patterns |

## Test Strategy

**Tests are NOT optional. Each component MUST have unit tests.**

- [ ] ContextEstimator: token counting, threshold detection, reset
- [ ] PhaseCheckpoint: progress recording, context formatting
- [ ] CheckpointManager: git state capture, restart preparation
- [ ] Auto-commit: success/failure paths, dirty directory handling
- [ ] Integration: full restart cycle with mocked runner

## Acceptance Criteria

**ALL criteria must be met before signaling completion:**

- [ ] Context estimator tracks file reads and tool outputs
- [ ] Threshold breach triggers graceful phase restart
- [ ] Restart prompt includes progress entries and git diff
- [ ] Auto-commit creates clean phase boundary commits
- [ ] Max restart limit prevents infinite loops
- [ ] All new code has unit tests
- [ ] All existing tests pass
- [ ] `uv run ruff check .` returns 0 errors
- [ ] `uv run pyright src/debussy/` returns 0 errors

## Rollback Plan

- Feature is additive - all functionality behind config flags
- Default `auto_commit: true` but can be disabled
- Context monitoring only active when threshold configured
- If issues found, set `context_threshold: 100` to effectively disable

---

## Configuration Reference

```yaml
# .debussy/config.yaml

# Context monitoring (Phase 6)
context_threshold: 80.0  # Restart when estimated usage hits 80%
tool_call_threshold: 100  # Fallback: restart after 100 tool calls
max_restarts: 3  # Give up after 3 restart attempts

# Auto-commit
auto_commit: true  # Commit at phase boundaries
commit_on_failure: false  # Only commit successful phases
```

## CLI Reference

```bash
# Run with context monitoring
debussy run MASTER_PLAN.md --context-threshold 80

# Run without auto-commit
debussy run MASTER_PLAN.md --no-auto-commit

# Allow dirty working directory
debussy run MASTER_PLAN.md --allow-dirty

# Disable restarts (one-shot mode)
debussy run MASTER_PLAN.md --max-restarts 0
```
