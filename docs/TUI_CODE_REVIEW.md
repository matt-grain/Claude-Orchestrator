# Textual TUI Code Review - Debussy Orchestrator

**Date:** 2026-01-13
**Reviewer:** textual-tui-expert agent
**Focus:** Error handling, graceful shutdown, subprocess cleanup

---

## Issue Tracker

| # | Issue | Severity | Status | Fix Location |
|---|-------|----------|--------|--------------|
| 1 | Worker reference never assigned | 🔴 Critical | ✅ Fixed | `tui.py:271` |
| 2 | No cleanup on crash/exception | 🔴 Critical | ✅ Fixed | `tui.py:273-309` + `claude.py:139-151` (atexit) |
| 3 | Race condition in quit flow | 🔴 Critical | ✅ Fixed | `tui.py:412-444` (`_graceful_shutdown`) |
| 4 | Process tree not killed (grandchildren orphaned) | 🔴 Critical | ✅ Fixed | `claude.py:281-327` (`_kill_process_tree`) |
| 5 | UI/business logic mixed in DebussyTUI | 🟡 Architecture | 📋 Planned | See `UI_LOGIC_SEPARATION_PLAN.md` |
| 6 | Duplicate UIContext instances | 🟡 Architecture | ✅ Fixed | `tui.py:640-646` (`TextualUI.context` property) |
| 7 | Unnecessary call_later() for async workers | 🟡 Architecture | ✅ Fixed | `tui.py:517-629` (removed 12 unnecessary calls) |
| 8 | Manual HUD refresh instead of reactive | 🟢 Optimization | ⏳ Deferred | Already uses reactive attributes; further optimization requires significant refactor |
| 9 | RichLog auto_scroll disabled | 🟢 Optimization | ✅ Fixed | `tui.py:437-447` (`action_toggle_autoscroll`) + `HotkeyBar.auto_scroll` reactive |
| 10 | Missing Worker type annotation | 🟢 Optimization | ✅ Fixed | `tui.py:267` |

### Additional Safety Mechanisms Implemented

| Mechanism | Description | Location |
|-----------|-------------|----------|
| PID Registry | Global singleton tracking all spawned Claude PIDs | `claude.py:31-155` |
| atexit Handler | Last-resort cleanup on Python exit | `claude.py:139-151` |
| Process Group Creation | Unix `start_new_session=True` for proper tree killing | `claude.py:312-313` |
| Final PID Verification | Double-check all PIDs are dead before exit | `tui.py:298-309` |

---

## Executive Summary

This is a well-structured Textual TUI application that orchestrates Claude CLI sessions. However, several critical issues related to subprocess cleanup could leave orphaned Claude processes running, along with architectural concerns and optimization opportunities.

---

## Critical Issues

### 1. Worker Reference Never Assigned - Subprocess Cleanup Broken

**File:** `src/debussy/ui/tui.py`
**Lines:** 252, 270, 272-277, 404-406

This is the most severe issue. The `_worker` field is never assigned, making subprocess cancellation impossible during quit.

```python
# Line 252: Worker field initialized to None
self._worker: Worker | None = None

# Line 270: Worker is started but return value not captured!
if self._orchestration_coro:
    self._start_orchestration()  # Returns a Worker, but discarded!

# Lines 404-406: Cancellation attempts to use non-existent worker
if self._worker:
    self._worker.cancel()  # self._worker is ALWAYS None!
```

**Impact:** When the user presses 'q' to quit, the code attempts to cancel `self._worker`, but since it is always `None`, the Claude subprocess continues running in the background.

**Fix:**
```python
def on_mount(self) -> None:
    """Start timer and orchestration when app mounts."""
    self.set_interval(1.0, self._update_timer)
    self.update_hud()

    # Start orchestration as a worker if provided
    if self._orchestration_coro:
        self._worker = self._start_orchestration()  # CAPTURE THE WORKER
```

---

### 2. No Cleanup on Unhandled Exceptions or App Crash

**File:** `src/debussy/ui/tui.py`

The TUI has no `on_unmount()`, `on_exception()`, or any cleanup handler for unexpected exits. If the app crashes or receives SIGTERM, Claude subprocesses will be orphaned.

**Fix:** Add exception handling and cleanup methods:
```python
class DebussyTUI(App):
    def on_unmount(self) -> None:
        """Cleanup when app unmounts (including crashes)."""
        self._cleanup_workers()

    def _cleanup_workers(self) -> None:
        """Cancel all running workers and wait for subprocess cleanup."""
        if self._worker and self._worker.is_running:
            self._worker.cancel()

    def on_exception(self, exception: Exception) -> None:
        """Handle unhandled exceptions - cleanup before crash."""
        self._cleanup_workers()
        super().on_exception(exception)
```

---

### 3. Race Condition in Quit Flow - Exit Before Subprocess Killed

**File:** `src/debussy/ui/tui.py`
**Lines:** 408-414

```python
def _handle_quit_confirmation(self, confirmed: bool | None) -> None:
    # ...
    if self._worker:
        self._worker.cancel()  # Async cancel initiated

    # Show cleanup message and exit after a brief delay
    self.set_timer(0.5, self._finish_quit)  # 0.5s may not be enough!

def _finish_quit(self) -> None:
    """Finish quitting after cleanup."""
    self.write_log("[green]All Claude instances cancelled. Cleanup complete.[/green]")
    self.set_timer(1.0, lambda: self.exit())  # Exits regardless of cleanup state
```

**Problem:** The quit flow uses fixed timers (0.5s + 1.0s) instead of waiting for actual subprocess termination. If the subprocess takes longer to die, the app exits while Claude is still running.

**Fix:** Wait for worker completion before exiting:
```python
def _handle_quit_confirmation(self, confirmed: bool | None) -> None:
    if not confirmed:
        self.set_hud_message("Quit cancelled")
        self.set_timer(2.0, self.clear_hud_message)
        return

    self._action_queue.append(UserAction.QUIT)
    self.write_log("")
    self.write_log("[yellow]Shutting down...[/yellow]")

    if self._worker and self._worker.is_running:
        self._worker.cancel()
        self._wait_for_worker_cleanup()
    else:
        self._finish_quit()

@work(thread=False, exclusive=True, group="cleanup")
async def _wait_for_worker_cleanup(self) -> None:
    """Wait for the orchestration worker to finish cleanup."""
    for _ in range(30):  # Max 3 seconds
        if self._worker is None or not self._worker.is_running:
            break
        await asyncio.sleep(0.1)

    self.call_later(self._finish_quit)
```

---

### 4. ClaudeRunner Subprocess Kill May Leave Grandchildren

**File:** `src/debussy/runners/claude.py`
**Lines:** 338-352

```python
except TimeoutError:
    process.kill()  # Kills only direct child, not grandchildren
    await process.wait()
```

**Problem:** `process.kill()` sends SIGKILL only to the direct child process. If Claude spawns any child processes (subagents, shell commands), they become orphans. On Windows, this is even more problematic as process trees are not killed.

**Fix:** Use process group killing for proper cleanup:
```python
import os
import signal
import sys

async def _kill_process_tree(self, process: asyncio.subprocess.Process) -> None:
    """Kill process and all descendants."""
    if process.returncode is not None:
        return

    pid = process.pid

    try:
        if sys.platform == "win32":
            # Windows: use taskkill for tree
            proc = await asyncio.create_subprocess_exec(
                "taskkill", "/F", "/T", "/PID", str(pid),
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            await proc.wait()
        else:
            # Unix: kill process group
            try:
                os.killpg(pid, signal.SIGTERM)
            except ProcessLookupError:
                pass

            # Give graceful shutdown time, then force kill
            try:
                await asyncio.wait_for(process.wait(), timeout=2.0)
            except asyncio.TimeoutError:
                with suppress(ProcessLookupError):
                    os.killpg(pid, signal.SIGKILL)
    except Exception:
        # Fallback to basic kill
        process.kill()

    await process.wait()
```

---

## Architecture Concerns

### 1. UI and Business Logic Mixed in DebussyTUI

**File:** `src/debussy/ui/tui.py`

The `DebussyTUI` class handles both UI rendering and orchestration lifecycle management. Methods like `start()`, `set_phase()`, and `update_token_stats()` are business logic that should live in a separate controller.

**Recommendation:** Extract the UI interface protocol and have the orchestrator communicate via messages:

```python
class PhaseChanged(Message):
    """Message when phase changes."""
    def __init__(self, phase_id: str, title: str, index: int) -> None:
        self.phase_id = phase_id
        self.title = title
        self.index = index
        super().__init__()
```

---

### 2. Duplicate UIContext Instances

**Files:** `src/debussy/ui/tui.py`

```python
class TextualUI:
    def __init__(self) -> None:
        self._app: DebussyTUI | None = None
        self.context = UIContext()  # One context here

class DebussyTUI(App):
    def __init__(self, ...):
        self.ui_context = UIContext()  # Another context here!
```

**Fix:** Remove the duplicate context from `TextualUI` or proxy to the app's context.

---

### 3. Unnecessary call_later() for Async Workers

**File:** `src/debussy/ui/tui.py`

Multiple methods use `self.call_later()` for UI updates, but since `_start_orchestration` uses `@work(exclusive=True)` without `thread=True`, the orchestration runs in the async event loop, not a thread. The `call_later()` calls are unnecessary and add latency.

---

## Optimization Opportunities

### 1. Use reactive() for HUD Updates Instead of Manual Refresh

The current pattern manually calls `update_hud()` after every change. The `HUDHeader` widget already has reactive attributes - leverage them fully to eliminate manual refresh calls.

---

### 2. RichLog auto_scroll is Disabled

**File:** `src/debussy/ui/tui.py`
**Line:** 261

```python
yield RichLog(id="log", highlight=True, markup=True, wrap=True, auto_scroll=False)
```

**Recommendation:** Enable `auto_scroll=True` by default with a toggle hotkey:
```python
Binding("a", "toggle_autoscroll", "Auto-scroll", show=False),
```

---

### 3. Missing Type Annotations for Worker

```python
self._worker: Worker | None = None
```

Should be:
```python
self._worker: Worker[str] | None = None  # Worker returns str (run_id)
```

---

## Summary

| Category | Count | Impact |
|----------|-------|--------|
| Critical Issues | 4 | Orphaned subprocesses, resource leaks |
| Architecture Concerns | 3 | Maintainability, testability |
| Optimizations | 4 | Performance, UX improvements |

---

## Priority Order for Fixes

1. **IMMEDIATE:** Fix `_worker` assignment (line 270) - one-line fix that enables subprocess cancellation
2. **HIGH:** Add `on_unmount()` and proper shutdown handling
3. **HIGH:** Implement process tree termination in `ClaudeRunner`
4. **MEDIUM:** Remove race condition in quit flow by waiting for actual cleanup
5. **LOW:** Architecture improvements and optimizations

---

The codebase demonstrates good understanding of Textual patterns (reactive attributes, workers, message system), but the subprocess lifecycle management needs immediate attention to prevent orphaned Claude processes.
