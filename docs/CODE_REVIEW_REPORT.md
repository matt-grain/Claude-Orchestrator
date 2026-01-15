# Debussy Codebase Review Report

**Date:** 2026-01-15
**Reviewer:** Python Task Validator
**Codebase Version:** v0.3.16 (commit 29dd78f)
**Total Lines of Code:** ~6,343

---

## Executive Summary

The Debussy codebase demonstrates competent Python engineering with good use of modern patterns (async/await, Pydantic models, Textual TUI). However, rapid growth has introduced concerning complexity in key modules, interface duplication between UI implementations, and several architectural issues that will compound technical debt if not addressed.

**Validation Status:** CONDITIONAL PASS

The codebase passes static analysis (pyright: 0 errors, ruff: clean, bandit: low severity only) but has structural issues requiring attention before further feature development.

### Key Metrics

| Metric | Value | Assessment |
|--------|-------|------------|
| Pyright Errors | 0 | Excellent |
| Ruff Violations | 0 | Excellent |
| Bandit High/Medium | 0 | Good |
| Bandit Low | 29 | Acceptable (subprocess use expected) |
| Average Complexity | A (2.93) | Good |
| High-Complexity Functions | 13 (C/D grade) | Needs Attention |
| Maintainability Index | 1 file at C (claude.py) | Needs Refactoring |

---

## Critical Issues (Must Fix)

### 1. [CRITICAL] ClaudeRunner God Class - Too Many Responsibilities

**Location:** `src/debussy/runners/claude.py` (1,208 lines)

**Problem:** The `ClaudeRunner` class has become a God class with at least 7 distinct responsibilities:
- Subprocess spawning and management
- JSON stream parsing
- Tool use display formatting
- Log file management
- Token statistics tracking
- Agent state management
- Docker/sandbox command building

**Evidence:**
```python
# Lines 247-288: Constructor with 14+ parameters
def __init__(
    self,
    project_root: Path,
    timeout: int = 1800,
    claude_command: str = "claude",
    stream_output: bool = True,
    model: str = "haiku",
    output_mode: OutputMode = "terminal",
    log_dir: Path | None = None,
    output_callback: Callable[[str], None] | None = None,
    token_stats_callback: Callable[[TokenStats], None] | None = None,
    agent_change_callback: Callable[[str], None] | None = None,
    with_ltm: bool = False,
    sandbox_mode: Literal["none", "devcontainer"] = "none",
) -> None:
```

**Impact:**
- Maintainability Index: C (8.07) - worst in codebase
- 8 methods with complexity grade C or worse
- Changes to any responsibility risk breaking others
- Unit testing requires mocking everything

**Recommendation:** Extract into focused classes:
```
ClaudeRunner (slim orchestrator)
 +-- ProcessSpawner (subprocess lifecycle)
 +-- JsonStreamParser (event parsing + display)
 +-- SessionLogger (file I/O)
 +-- DockerCommandBuilder (sandbox logic)
```

---

### 2. [CRITICAL] CLI Module Excessive Complexity

**Location:** `src/debussy/cli.py` (1,344 lines)

**Problem:** Two CLI commands exceed acceptable complexity thresholds:
- `audit()`: Complexity D (very high)
- `run()`: Complexity D (very high)

**Evidence from radon:**
```
F 397:0 audit - D
F 157:0 run - D
F 592:0 plan_init - C
F 697:0 convert - C
```

**Impact:**
- Maintainability Index: B (17.53) - below ideal
- Difficult to test individual behaviors
- Cognitive load makes bugs likely

**Recommendation:** Extract helper functions and consider a command pattern:

```python
# Instead of one massive run() function:
class RunCommand:
    def validate_flags(self) -> None: ...
    def check_resumable(self) -> set[str] | None: ...
    def prompt_security_warning(self) -> bool: ...
    def execute(self) -> str: ...
```

---

### 3. [CRITICAL] UI Interface Duplication

**Location:**
- `src/debussy/ui/tui.py` (DebussyTUI, TextualUI)
- `src/debussy/ui/interactive.py` (NonInteractiveUI)
- `src/debussy/ui/controller.py` (OrchestrationController)

**Problem:** Three classes implement the same UI interface with copy-pasted method signatures but no shared protocol/ABC. This violates DRY and makes interface changes error-prone.

**Evidence:**

`TextualUI` wrapper (lines 850-978):
```python
def start(self, plan_name: str, total_phases: int) -> None:
def stop(self) -> None:
def set_phase(self, phase: Phase, index: int) -> None:
def set_state(self, state: UIState) -> None:
def log(self, message: str) -> None:
def log_message(self, message: str) -> None:
def log_raw(self, message: str) -> None:
def get_pending_action(self) -> UserAction:
def toggle_verbose(self) -> bool:
def show_status_popup(self, details: dict[str, str]) -> None:
def confirm(self, message: str) -> bool:
def update_token_stats(...) -> None:
def set_active_agent(self, agent: str) -> None:
def set_model(self, model: str) -> None:
```

`NonInteractiveUI` (lines 16-115) - identical method signatures.

**Impact:**
- No compile-time interface enforcement
- Orchestrator uses `hasattr()` checks instead of proper typing
- Adding new UI methods requires changes in 3+ places

**Recommendation:** Define a Protocol or ABC:

```python
from typing import Protocol

class OrchestratorUI(Protocol):
    """Protocol for UI implementations."""

    def start(self, plan_name: str, total_phases: int) -> None: ...
    def stop(self) -> None: ...
    def set_phase(self, phase: Phase, index: int) -> None: ...
    def set_state(self, state: UIState) -> None: ...
    def log_message(self, message: str) -> None: ...
    def log_raw(self, message: str) -> None: ...
    def get_pending_action(self) -> UserAction: ...
    # ... etc
```

---

## Serious Issues (Should Fix)

### 4. [HIGH] Orchestrator Direct Attribute Access

**Location:** `src/debussy/core/orchestrator.py:74-77`

**Problem:** The Orchestrator reaches into ClaudeRunner's internals to set callbacks:

```python
# Line 74-77
self.claude._output_callback = self.ui.log
if self.config.interactive:
    self.claude._token_stats_callback = self._on_token_stats
    self.claude._agent_change_callback = self._on_agent_change
```

**Impact:**
- Tight coupling between Orchestrator and ClaudeRunner internals
- Underscore prefix implies private attribute
- No validation of callback compatibility

**Recommendation:** Use constructor injection or a proper setter:

```python
# In ClaudeRunner:
def set_callbacks(
    self,
    output: Callable[[str], None] | None = None,
    token_stats: Callable[[TokenStats], None] | None = None,
    agent_change: Callable[[str], None] | None = None,
) -> None:
    """Configure runtime callbacks."""
    self._output_callback = output
    self._token_stats_callback = token_stats
    self._agent_change_callback = agent_change
```

---

### 5. [HIGH] hasattr() Duck Typing in Orchestrator

**Location:** `src/debussy/core/orchestrator.py:82-96`

**Problem:** Using `hasattr()` checks instead of proper interface enforcement:

```python
def _on_token_stats(self, stats: TokenStats) -> None:
    if hasattr(self.ui, "update_token_stats"):  # Line 84
        self.ui.update_token_stats(...)

def _on_agent_change(self, agent: str) -> None:
    if hasattr(self.ui, "set_active_agent"):  # Line 95
        self.ui.set_active_agent(agent)
```

**Impact:**
- Silent failures if method is misspelled or missing
- No IDE autocomplete or type checking
- Code smell indicating missing interface definition

**Recommendation:** Once a Protocol is defined, remove hasattr checks and use proper typing.

---

### 6. [HIGH] Duplicate Path Normalization Logic

**Location:**
- `src/debussy/runners/claude.py:75-91` (`_normalize_path_for_docker`)
- `src/debussy/cli.py:1242-1254` (`_wsl_path`)

**Problem:** Two nearly-identical functions convert Windows paths for Docker/WSL:

`runners/claude.py`:
```python
def _normalize_path_for_docker(path: Path, use_wsl: bool = False) -> str:
    if platform.system() == "Windows":
        path_str = str(path.resolve())
        if len(path_str) >= 2 and path_str[1] == ":":
            drive = path_str[0].lower()
            rest = path_str[2:].replace("\\", "/")
            if use_wsl:
                return f"/mnt/{drive}{rest}"
            return f"/{drive}{rest}"
    return str(path)
```

`cli.py`:
```python
def _wsl_path(path: Path) -> str:
    if platform.system() != "Windows":
        return str(path)
    path_str = str(path.resolve())
    if len(path_str) >= 2 and path_str[1] == ":":
        drive = path_str[0].lower()
        rest = path_str[2:].replace("\\", "/")
        return f"/mnt/{drive}{rest}"
    return str(path)
```

**Impact:**
- DRY violation
- Bug fixes must be applied to both locations
- Subtle differences in behavior (one always uses /mnt/, other is conditional)

**Recommendation:** Extract to a shared utility module:

```python
# src/debussy/utils/paths.py
def windows_path_to_docker(path: Path, mount_prefix: str = "/mnt") -> str:
    """Convert Windows path to Docker volume mount format."""
    ...
```

---

### 7. [HIGH] Duplicate Docker Availability Checks

**Location:**
- `src/debussy/runners/claude.py:31-38` (`_get_docker_command`)
- `src/debussy/cli.py:1229-1240` (`_get_docker_command`)

**Problem:** Identical function defined in two places:

```python
# Both files:
def _get_docker_command() -> list[str]:
    if shutil.which("docker"):
        return ["docker"]
    if platform.system() == "Windows" and shutil.which("wsl"):
        return ["wsl", "docker"]
    return ["docker"]
```

**Recommendation:** Consolidate into runners/claude.py and import in cli.py:

```python
from debussy.runners.claude import get_docker_command
```

---

### 8. [HIGH] Mutable Token Statistics State

**Location:** `src/debussy/ui/controller.py:130-175`

**Problem:** Token statistics are tracked with mutable state that's easy to corrupt:

```python
def update_token_stats(self, ...):
    self.context.session_input_tokens = input_tokens
    self.context.session_output_tokens = output_tokens
    # ...
    if cost_usd > 0:
        self.context.total_input_tokens += input_tokens  # Accumulation
        self.context.total_output_tokens += output_tokens
        self.context.total_cost_usd += cost_usd
```

**Impact:**
- Session tokens are overwritten each call (correct)
- Total tokens are accumulated only when cost > 0 (fragile condition)
- Easy to double-count or miss updates

**Recommendation:** Use an immutable accumulator pattern:

```python
@dataclass(frozen=True)
class SessionStats:
    input_tokens: int
    output_tokens: int
    cost_usd: float

class TokenAccumulator:
    def record_session(self, stats: SessionStats) -> None:
        self._sessions.append(stats)

    @property
    def total_cost(self) -> float:
        return sum(s.cost_usd for s in self._sessions)
```

---

## Medium Issues (Should Address)

### 9. [MEDIUM] Bare Exception Handlers

**Location:** `src/debussy/cli.py:585-586`

**Problem:** Swallowing all exceptions silently:

```python
try:
    detailed = parse_phase(phase.path, phase.id)
    # ...
except Exception:
    pass  # Skip details if parsing fails
```

**Impact:**
- Hides genuine bugs during development
- Makes debugging difficult in production

**Recommendation:** At minimum, log the exception:

```python
except Exception:
    logger.debug(f"Could not parse phase details for {phase.path}: {e}")
```

---

### 10. [MEDIUM] Assert Statements in Production Code

**Location:** `src/debussy/runners/claude.py:940-941`

**Problem:** Using `assert` for runtime validation:

```python
assert process.stdout is not None
assert process.stderr is not None
```

**Impact:**
- Asserts are stripped in optimized mode (`python -O`)
- Production code would fail with cryptic AttributeError

**Recommendation:** Use explicit validation:

```python
if process.stdout is None or process.stderr is None:
    raise RuntimeError("Subprocess streams not initialized")
```

---

### 11. [MEDIUM] Singleton Pattern via __new__ Override

**Location:** `src/debussy/runners/claude.py:101-118`

**Problem:** PIDRegistry uses `__new__` for singleton pattern:

```python
class PIDRegistry:
    _instance: PIDRegistry | None = None

    def __new__(cls) -> PIDRegistry:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._pids = set()
            cls._instance._atexit_registered = False
        return cls._instance
```

**Impact:**
- Makes testing difficult (global state persists)
- Thread-safety concerns (no lock)
- `__new__` override is considered a Python anti-pattern

**Recommendation:** Use a module-level factory or dependency injection:

```python
_registry: PIDRegistry | None = None

def get_pid_registry() -> PIDRegistry:
    global _registry
    if _registry is None:
        _registry = PIDRegistry()
    return _registry

# For testing:
def reset_pid_registry() -> None:
    global _registry
    _registry = None
```

---

### 12. [MEDIUM] Magic Numbers

**Location:** Multiple files

**Problem:** Several magic numbers without named constants:

```python
# runners/claude.py:553
line_limit = 2 * 1024 * 1024  # 2MB

# runners/claude.py:239, ui/base.py:51, ui/controller.py:136
context_window: int = 200_000  # Default Claude context

# cli.py:33
__version__ = "0.1.1"  # Hardcoded, not synced with pyproject.toml
```

**Recommendation:** Extract to constants module:

```python
# src/debussy/constants.py
CLAUDE_DEFAULT_CONTEXT_WINDOW = 200_000
SUBPROCESS_LINE_LIMIT = 2 * 1024 * 1024  # 2MB
```

---

### 13. [MEDIUM] Type Annotation Missing on UI Field

**Location:** `src/debussy/core/orchestrator.py:70`

**Problem:** UI type annotation allows either type but no union:

```python
self.ui: TextualUI | NonInteractiveUI = TextualUI() if self.config.interactive else NonInteractiveUI()
```

**Impact:**
- Works but fragile if third UI type added
- Should use the Protocol type once defined

---

## Minor Issues (Low Priority)

### 14. [LOW] Import Inside Function

**Location:** Multiple locations

**Problem:** Several deferred imports inside functions:

```python
# cli.py:234
from debussy.core.auditor import PlanAuditor

# cli.py:254
from debussy.config import Config

# cli.py:356-358
from debussy.config import Config
from debussy.core.orchestrator import Orchestrator
from debussy.ui.tui import DebussyTUI
```

**Assessment:** These appear intentional for startup performance. Acceptable pattern but should be documented.

---

### 15. [LOW] Inconsistent Log Method Naming

**Location:** UI classes

**Problem:** Multiple aliases for the same behavior:

```python
# TextualUI
def log(self, message: str) -> None:
def log_message(self, message: str) -> None:  # Same as log
def log_raw(self, message: str) -> None:

# NonInteractiveUI
def log(self, message: str) -> None:
log_message = log  # Alias
def log_raw(self, message: str) -> None:
```

**Recommendation:** Pick one canonical name and deprecate aliases.

---

### 16. [LOW] Bandit Low-Severity Subprocess Findings

**Location:** Multiple files (29 findings)

**Assessment:** All findings are related to subprocess usage which is fundamental to this tool's purpose. The code correctly uses `check=False` and handles errors. No action required, but consider adding `# nosec` comments with explanations.

---

## Architectural Observations

### What Works Well

1. **Clean Data Models:** Pydantic models in `core/models.py` are well-structured with good field defaults and enums.

2. **Compliance Checker Design:** The `ComplianceChecker` in `core/compliance.py` has a clean separation of concerns with focused methods for each check type.

3. **Message-Based TUI Communication:** The controller/message pattern in `ui/controller.py` and `ui/messages.py` is a solid architecture choice.

4. **Gate Runner Simplicity:** `runners/gates.py` is focused and testable at 126 lines.

5. **Notification Provider Pattern:** The `Notifier` ABC with `CompositeNotifier` in notifications/ is extensible and clean.

### What Needs Work

1. **ClaudeRunner Needs Decomposition:** The 1,200-line class should become a small coordination layer over focused components.

2. **UI Interface Needs Formalization:** Define a Protocol, implement it in both UI classes, type the Orchestrator.ui field properly.

3. **CLI Commands Too Large:** Extract common patterns (audit display, security prompts) into helper classes.

4. **Shared Utilities Missing:** Path conversion and Docker checks should be in a utils module.

---

## Priority Order for Fixes

| Priority | Issue | Effort | Impact |
|----------|-------|--------|--------|
| 1 | Define UI Protocol/ABC | Low | High - enables proper typing |
| 2 | Extract path utilities | Low | Medium - DRY cleanup |
| 3 | Replace hasattr() with Protocol typing | Low | Medium - type safety |
| 4 | Replace asserts with explicit validation | Low | Medium - production safety |
| 5 | Extract ClaudeRunner components | High | High - maintainability |
| 6 | Refactor CLI commands | Medium | Medium - testability |
| 7 | Consolidate token tracking | Medium | Low - code clarity |
| 8 | Add constants module | Low | Low - readability |

---

## Testing Recommendations

The codebase has tests but they would benefit from:

1. **Unit tests for ClaudeRunner subcomponents** (after extraction)
2. **Protocol compliance tests** for UI implementations
3. **Integration tests with mocked subprocess** for Docker commands
4. **Property-based tests** for path conversion functions

---

## Conclusion

This codebase is functional and passes static analysis, but has accumulated complexity in key modules that will impede future development. The highest-priority fix is defining a proper UI Protocol - this is low effort with high impact on type safety and maintainability. The ClaudeRunner decomposition is higher effort but essential before adding more features to that module.

**Recommended Action:** Address Priority 1-4 issues before any new feature work. Schedule Priority 5-6 as dedicated refactoring sprints.

---

*Report generated by Python Task Validator*
