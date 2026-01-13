# UI/Logic Separation Architecture Plan

**Issue:** #5 from TUI_CODE_REVIEW.md - "UI/business logic mixed in DebussyTUI"
**Date:** 2026-01-13
**Status:** Architecture Plan (Pre-Implementation)

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Current State Analysis](#current-state-analysis)
3. [Target Architecture](#target-architecture)
4. [Message Protocol Design](#message-protocol-design)
5. [Implementation Tasks](#implementation-tasks)
6. [Code Examples](#code-examples)
7. [Testing Strategy](#testing-strategy)
8. [Migration Path](#migration-path)
9. [Risk Mitigation](#risk-mitigation)

---

## Executive Summary

The `DebussyTUI` class currently mixes UI rendering with orchestration lifecycle management, violating the separation of concerns principle. This plan outlines a refactor to:

1. **Extract orchestration state management** into a dedicated `OrchestrationController`
2. **Introduce a Message-based protocol** for UI/controller communication
3. **Make the TUI a pure view layer** that only renders state and forwards user input
4. **Improve testability** by enabling headless controller testing

### Key Benefits

- **Testability**: Controller logic can be unit tested without TUI
- **Maintainability**: Clear boundaries make changes safer
- **Reusability**: Controller can be used by other UIs (web dashboard, API)
- **Textual Best Practices**: Aligns with the framework's message-driven architecture

---

## Current State Analysis

### Business Logic Currently in DebussyTUI

The following responsibilities are embedded directly in `DebussyTUI` (lines referenced from `src/debussy/ui/tui.py`):

#### 1. Orchestration State Management

| Location | Responsibility | Should Be In |
|----------|---------------|--------------|
| Line 264 | `UIContext()` instantiation | Controller |
| Line 265 | `_action_queue: deque[UserAction]` | Controller |
| Line 517-525 | `start()` - initializes orchestration state | Controller |
| Line 546-552 | `set_phase()` - updates phase state | Controller |
| Line 554-557 | `set_state()` - updates UI state | Controller |
| Line 588-613 | `update_token_stats()` - token accounting | Controller |

#### 2. Phase Tracking Logic

```python
# Line 546-552: Phase management mixed with UI updates
def set_phase(self, phase: Phase, index: int) -> None:
    """Update the current phase being executed."""
    self.ui_context.current_phase = phase.id      # State management
    self.ui_context.phase_title = phase.title     # State management
    self.ui_context.phase_index = index           # State management
    self.ui_context.start_time = time.time()      # Business logic
    self.call_later(self.update_hud)              # UI update
```

#### 3. Token Tracking Calculations

```python
# Lines 588-613: Business logic for cost accumulation
def update_token_stats(self, ...):
    # Session tracking (state)
    self.ui_context.session_input_tokens = input_tokens
    # Cost accumulation logic (business logic)
    if cost_usd > 0:
        self.ui_context.total_input_tokens += input_tokens
        self.ui_context.total_cost_usd += cost_usd
```

#### 4. Action Queue Management

```python
# Line 265: Queue lives in TUI
self._action_queue: deque[UserAction] = deque()

# Line 572-578: Queue manipulation in TUI
def get_pending_action(self) -> UserAction:
    if self._action_queue:
        action = self._action_queue.popleft()
        self.ui_context.last_action = action
        return action
    return UserAction.NONE
```

#### 5. Worker Lifecycle Management

```python
# Lines 286-287: Worker spawning in TUI
if self._orchestration_coro:
    self._worker = self._start_orchestration()

# Lines 479-511: Shutdown logic in TUI
async def _graceful_shutdown(self) -> None:
    # Business logic for graceful shutdown
```

### Problems with Current Design

1. **Untestable UI Logic**: Testing phase transitions requires a full TUI
2. **Duplicate State**: `TextualUI.context` vs `DebussyTUI.ui_context`
3. **Tight Coupling**: Orchestrator calls TUI methods directly (procedural)
4. **Mixed Responsibilities**: `action_toggle_pause` both queues action AND shows message
5. **Implicit State Machine**: UI state transitions scattered across methods

---

## Target Architecture

### High-Level Design

```
┌─────────────────────────────────────────────────────────────────┐
│                        Orchestrator                              │
│  (orchestrator.py - unchanged, uses UI protocol)                │
└─────────────────────────────────────────────────────────────────┘
                              │
                              │ UI Protocol (unchanged interface)
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    OrchestrationController                       │
│  ┌────────────────┐  ┌──────────────┐  ┌───────────────────┐   │
│  │  State Machine │  │ Action Queue │  │ Token Accumulator │   │
│  └────────────────┘  └──────────────┘  └───────────────────┘   │
│                                                                  │
│  - Owns UIContext singleton                                      │
│  - Processes user actions                                        │
│  - Emits Messages to TUI                                         │
│  - Receives Messages from TUI                                    │
└─────────────────────────────────────────────────────────────────┘
                              │
                              │ Textual Messages
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                        DebussyTUI                                │
│                                                                  │
│  Pure View Layer:                                                │
│  - Renders state from messages                                   │
│  - Forwards key presses as messages                              │
│  - No business logic                                             │
│  - No UIContext ownership                                        │
└─────────────────────────────────────────────────────────────────┘
```

### New Module Structure

```
src/debussy/ui/
├── __init__.py           # Exports (add OrchestrationController)
├── base.py               # UIContext, UIState, UserAction (unchanged)
├── controller.py         # NEW: OrchestrationController
├── messages.py           # NEW: Message types
├── interactive.py        # NonInteractiveUI (unchanged)
└── tui.py                # DebussyTUI (refactored to pure view)
```

### Responsibility Matrix

| Component | Responsibilities |
|-----------|-----------------|
| **OrchestrationController** | State management, action queue, token accounting, worker lifecycle |
| **DebussyTUI** | Widget composition, key binding handlers, message posting, rendering |
| **HUDHeader** | Render phase/status/timer from reactive attributes (unchanged) |
| **HotkeyBar** | Render hotkey hints and status messages (unchanged) |
| **Messages** | Type-safe communication between controller and TUI |

---

## Message Protocol Design

### Controller-to-TUI Messages (Commands)

These messages flow from the controller to update the TUI display:

```python
# src/debussy/ui/messages.py

from textual.message import Message
from debussy.ui.base import UIState


class OrchestrationStarted(Message):
    """Orchestration has started."""

    def __init__(self, plan_name: str, total_phases: int) -> None:
        self.plan_name = plan_name
        self.total_phases = total_phases
        super().__init__()


class PhaseChanged(Message):
    """Current phase has changed."""

    def __init__(
        self,
        phase_id: str,
        phase_title: str,
        phase_index: int,
        total_phases: int,
    ) -> None:
        self.phase_id = phase_id
        self.phase_title = phase_title
        self.phase_index = phase_index
        self.total_phases = total_phases
        super().__init__()


class StateChanged(Message):
    """UI state has changed (running, paused, etc.)."""

    def __init__(self, state: UIState) -> None:
        self.state = state
        super().__init__()


class TokenStatsUpdated(Message):
    """Token usage statistics have been updated."""

    def __init__(
        self,
        session_input_tokens: int,
        session_output_tokens: int,
        total_cost_usd: float,
        context_pct: int,
    ) -> None:
        self.session_input_tokens = session_input_tokens
        self.session_output_tokens = session_output_tokens
        self.total_cost_usd = total_cost_usd
        self.context_pct = context_pct
        super().__init__()


class LogMessage(Message):
    """Log message to display in the log panel."""

    def __init__(self, message: str, raw: bool = False) -> None:
        self.message = message
        self.raw = raw  # If True, bypasses verbose check
        super().__init__()


class HUDMessageSet(Message):
    """Transient message to show in hotkey bar."""

    def __init__(self, message: str, clear_after: float = 3.0) -> None:
        self.message = message
        self.clear_after = clear_after
        super().__init__()


class VerboseToggled(Message):
    """Verbose mode has been toggled."""

    def __init__(self, verbose: bool) -> None:
        self.verbose = verbose
        super().__init__()


class OrchestrationCompleted(Message):
    """Orchestration has completed (success or failure)."""

    def __init__(self, run_id: str, success: bool, message: str) -> None:
        self.run_id = run_id
        self.success = success
        self.message = message
        super().__init__()
```

### TUI-to-Controller Messages (Events)

These messages flow from the TUI when the user takes action:

```python
class UserActionRequested(Message):
    """User has requested an action via keyboard."""

    def __init__(self, action: UserAction) -> None:
        self.action = action
        super().__init__()


class ShutdownRequested(Message):
    """User has requested shutdown (after confirmation)."""
    pass


class StatusDetailsRequested(Message):
    """User wants to see status details."""
    pass
```

---

## Implementation Tasks

### Phase 1: Foundation (No Breaking Changes)

**Goal:** Create new modules without modifying existing behavior.

#### Task 1.1: Create Message Types Module
- **File:** `src/debussy/ui/messages.py`
- **Content:** All message classes defined above
- **Risk:** None (additive only)

#### Task 1.2: Create OrchestrationController Skeleton
- **File:** `src/debussy/ui/controller.py`
- **Content:** Basic class with UIContext ownership
- **Risk:** None (not yet used)

```python
# src/debussy/ui/controller.py

from collections import deque
from typing import TYPE_CHECKING

from textual.message import Message
from textual.app import App

from debussy.ui.base import UIContext, UIState, UserAction

if TYPE_CHECKING:
    from debussy.core.models import Phase


class OrchestrationController:
    """Manages orchestration state and emits UI messages.

    This controller owns all orchestration state and business logic.
    The TUI subscribes to messages and renders accordingly.
    """

    def __init__(self, app: App) -> None:
        self._app = app
        self.context = UIContext()
        self._action_queue: deque[UserAction] = deque()

    def _post(self, message: Message) -> None:
        """Post a message to the TUI."""
        self._app.post_message(message)
```

### Phase 2: Controller Implementation

**Goal:** Implement all business logic in the controller.

#### Task 2.1: Implement State Management Methods

```python
def start(self, plan_name: str, total_phases: int) -> None:
    """Initialize orchestration state."""
    self.context.plan_name = plan_name
    self.context.total_phases = total_phases
    self.context.start_time = time.time()
    self.context.state = UIState.RUNNING
    self._post(OrchestrationStarted(plan_name, total_phases))

def set_phase(self, phase: Phase, index: int) -> None:
    """Update current phase."""
    self.context.current_phase = phase.id
    self.context.phase_title = phase.title
    self.context.phase_index = index
    self.context.start_time = time.time()
    self._post(PhaseChanged(
        phase_id=phase.id,
        phase_title=phase.title,
        phase_index=index,
        total_phases=self.context.total_phases,
    ))
```

#### Task 2.2: Implement Token Tracking

```python
def update_token_stats(
    self,
    input_tokens: int,
    output_tokens: int,
    cost_usd: float,
    context_tokens: int,
    context_window: int = 200_000,
) -> None:
    """Update token statistics and emit message."""
    # Session tracking
    self.context.session_input_tokens = input_tokens
    self.context.session_output_tokens = output_tokens
    self.context.current_context_tokens = context_tokens
    self.context.context_window = context_window

    # Accumulate on final result
    if cost_usd > 0:
        self.context.total_input_tokens += input_tokens
        self.context.total_output_tokens += output_tokens
        self.context.total_cost_usd += cost_usd

    # Calculate context percentage
    context_pct = 0
    if context_window > 0 and context_tokens > 0:
        context_pct = int((context_tokens / context_window) * 100)

    session_tokens = input_tokens + output_tokens
    self._post(TokenStatsUpdated(
        session_input_tokens=session_tokens,
        session_output_tokens=output_tokens,
        total_cost_usd=self.context.total_cost_usd,
        context_pct=context_pct,
    ))
```

#### Task 2.3: Implement Action Queue Management

```python
def queue_action(self, action: UserAction) -> None:
    """Queue a user action for processing."""
    self._action_queue.append(action)

    # Emit appropriate feedback message
    feedback_map = {
        UserAction.PAUSE: "Pause requested (after current operation)",
        UserAction.RESUME: "Resume requested",
        UserAction.SKIP: "Skip requested (after current operation)",
    }
    if action in feedback_map:
        self._post(HUDMessageSet(feedback_map[action]))

def get_pending_action(self) -> UserAction:
    """Get and remove next pending action."""
    if self._action_queue:
        action = self._action_queue.popleft()
        self.context.last_action = action
        return action
    return UserAction.NONE
```

#### Task 2.4: Implement Verbose Toggle

```python
def toggle_verbose(self) -> bool:
    """Toggle verbose mode and emit message."""
    self.context.verbose = not self.context.verbose
    self._post(VerboseToggled(self.context.verbose))
    state_str = "ON" if self.context.verbose else "OFF"
    self._post(HUDMessageSet(f"Verbose: {state_str}"))
    return self.context.verbose
```

### Phase 3: TUI Refactor

**Goal:** Convert TUI to pure view layer.

#### Task 3.1: Remove UIContext from TUI

```python
# BEFORE (tui.py)
class DebussyTUI(App):
    def __init__(self, ...):
        self.ui_context = UIContext()  # Remove this

# AFTER
class DebussyTUI(App):
    def __init__(self, controller: OrchestrationController, ...):
        self._controller = controller  # Use controller's context
```

#### Task 3.2: Convert Action Handlers to Message Posters

```python
# BEFORE
def action_toggle_pause(self) -> None:
    if self.ui_context.state == UIState.RUNNING:
        self._action_queue.append(UserAction.PAUSE)
        self.set_hud_message("Pause requested...")
    else:
        self._action_queue.append(UserAction.RESUME)
        self.set_hud_message("Resume requested")
    self.set_timer(3.0, self.clear_hud_message)

# AFTER
def action_toggle_pause(self) -> None:
    state = self._controller.context.state
    action = UserAction.PAUSE if state == UIState.RUNNING else UserAction.RESUME
    self._controller.queue_action(action)
```

#### Task 3.3: Add Message Handlers

```python
def on_phase_changed(self, message: PhaseChanged) -> None:
    """Handle phase change from controller."""
    header = self.query_one("#hud-header", HUDHeader)
    header.phase_info = f"{message.phase_index}/{message.total_phases}: {message.phase_title}"

def on_state_changed(self, message: StateChanged) -> None:
    """Handle state change from controller."""
    header = self.query_one("#hud-header", HUDHeader)
    status_text, status_style = STATUS_MAP.get(message.state, ("Unknown", "white"))
    header.status = status_text
    header.status_style = status_style

def on_token_stats_updated(self, message: TokenStatsUpdated) -> None:
    """Handle token stats update from controller."""
    header = self.query_one("#hud-header", HUDHeader)
    header.total_tokens = message.session_input_tokens
    header.cost_usd = message.total_cost_usd
    header.context_pct = message.context_pct

def on_log_message(self, message: LogMessage) -> None:
    """Handle log message from controller."""
    if message.raw or self._controller.context.verbose:
        self.write_log(message.message)

def on_hud_message_set(self, message: HUDMessageSet) -> None:
    """Handle HUD message from controller."""
    self.set_hud_message(message.message)
    if message.clear_after > 0:
        self.set_timer(message.clear_after, self.clear_hud_message)
```

### Phase 4: Integration

**Goal:** Wire everything together.

#### Task 4.1: Update TextualUI Wrapper

```python
class TextualUI:
    """Wrapper that provides the UI interface backed by DebussyTUI."""

    def __init__(self) -> None:
        self._app: DebussyTUI | None = None
        self._controller: OrchestrationController | None = None

    def create_app(self, orchestration_coro=None) -> DebussyTUI:
        self._app = DebussyTUI(orchestration_coro=orchestration_coro)
        self._controller = OrchestrationController(self._app)
        self._app.set_controller(self._controller)
        return self._app

    # Proxy methods delegate to controller
    def start(self, plan_name: str, total_phases: int) -> None:
        if self._controller:
            self._controller.start(plan_name, total_phases)
```

#### Task 4.2: Update Exports

```python
# src/debussy/ui/__init__.py
from debussy.ui.base import UIContext, UIState, UserAction
from debussy.ui.controller import OrchestrationController
from debussy.ui.interactive import NonInteractiveUI
from debussy.ui.messages import (
    OrchestrationStarted,
    PhaseChanged,
    StateChanged,
    TokenStatsUpdated,
    LogMessage,
    HUDMessageSet,
    VerboseToggled,
    OrchestrationCompleted,
    UserActionRequested,
    ShutdownRequested,
)
from debussy.ui.tui import TextualUI

__all__ = [
    "NonInteractiveUI",
    "TextualUI",
    "OrchestrationController",
    "UIContext",
    "UIState",
    "UserAction",
    # Messages
    "OrchestrationStarted",
    "PhaseChanged",
    "StateChanged",
    "TokenStatsUpdated",
    "LogMessage",
    "HUDMessageSet",
    "VerboseToggled",
    "OrchestrationCompleted",
    "UserActionRequested",
    "ShutdownRequested",
]
```

---

## Code Examples

### Before: Mixed Responsibilities

```python
# tui.py - CURRENT STATE
class DebussyTUI(App):
    def __init__(self, orchestration_coro=None, **kwargs):
        super().__init__(**kwargs)
        self.ui_context = UIContext()                    # State
        self._action_queue: deque[UserAction] = deque()  # Business logic
        self._orchestration_coro = orchestration_coro
        self._worker: Worker[str] | None = None

    def action_toggle_verbose(self) -> None:
        """Handle verbose toggle - apply immediately in TUI."""
        # PROBLEM: Business logic mixed with UI
        self.ui_context.verbose = not self.ui_context.verbose  # State mutation
        self.update_hud()                                       # UI update
        state_str = "ON" if self.ui_context.verbose else "OFF"
        self.set_hud_message(f"Verbose: {state_str}")          # UI update
        self.set_timer(3.0, self.clear_hud_message)            # UI update

    def update_token_stats(self, input_tokens, output_tokens, cost_usd, ...):
        """Update token usage statistics."""
        # PROBLEM: Business logic in UI class
        self.ui_context.session_input_tokens = input_tokens
        if cost_usd > 0:
            self.ui_context.total_input_tokens += input_tokens  # Accumulation logic
            self.ui_context.total_cost_usd += cost_usd          # Accumulation logic
        self.call_later(self.update_hud)
```

### After: Clean Separation

```python
# controller.py - NEW
class OrchestrationController:
    """Pure business logic, no UI knowledge."""

    def __init__(self, app: App) -> None:
        self._app = app
        self.context = UIContext()
        self._action_queue: deque[UserAction] = deque()

    def toggle_verbose(self) -> bool:
        """Toggle verbose mode - pure state change."""
        self.context.verbose = not self.context.verbose
        self._post(VerboseToggled(self.context.verbose))
        state_str = "ON" if self.context.verbose else "OFF"
        self._post(HUDMessageSet(f"Verbose: {state_str}"))
        return self.context.verbose

    def update_token_stats(self, input_tokens, output_tokens, cost_usd, ...):
        """Token accounting - pure business logic."""
        self.context.session_input_tokens = input_tokens
        if cost_usd > 0:
            self.context.total_input_tokens += input_tokens
            self.context.total_cost_usd += cost_usd

        context_pct = int((context_tokens / context_window) * 100)
        self._post(TokenStatsUpdated(
            session_input_tokens=input_tokens + output_tokens,
            session_output_tokens=output_tokens,
            total_cost_usd=self.context.total_cost_usd,
            context_pct=context_pct,
        ))


# tui.py - REFACTORED
class DebussyTUI(App):
    """Pure view layer - renders and forwards input."""

    def __init__(self, orchestration_coro=None, **kwargs):
        super().__init__(**kwargs)
        self._controller: OrchestrationController | None = None
        self._orchestration_coro = orchestration_coro

    def set_controller(self, controller: OrchestrationController) -> None:
        """Inject the controller (set by TextualUI wrapper)."""
        self._controller = controller

    def action_toggle_verbose(self) -> None:
        """Forward verbose toggle to controller."""
        if self._controller:
            self._controller.toggle_verbose()

    # Message handlers - pure rendering
    def on_verbose_toggled(self, message: VerboseToggled) -> None:
        """Update hotkey bar verbose state."""
        hotkey_bar = self.query_one("#hotkey-bar", HotkeyBar)
        hotkey_bar.verbose = message.verbose

    def on_hud_message_set(self, message: HUDMessageSet) -> None:
        """Show transient message in HUD."""
        self.set_hud_message(message.message)
        if message.clear_after > 0:
            self.set_timer(message.clear_after, self.clear_hud_message)

    def on_token_stats_updated(self, message: TokenStatsUpdated) -> None:
        """Update HUD with token stats."""
        header = self.query_one("#hud-header", HUDHeader)
        header.total_tokens = message.session_input_tokens
        header.cost_usd = message.total_cost_usd
        header.context_pct = message.context_pct
```

---

## Testing Strategy

### Unit Testing the Controller

The controller can now be tested without any TUI:

```python
# tests/test_controller.py

import pytest
from unittest.mock import Mock, MagicMock

from debussy.ui.controller import OrchestrationController
from debussy.ui.base import UIState, UserAction
from debussy.ui.messages import (
    OrchestrationStarted,
    PhaseChanged,
    TokenStatsUpdated,
    VerboseToggled,
)


class TestOrchestrationController:
    """Unit tests for OrchestrationController."""

    @pytest.fixture
    def mock_app(self):
        """Create a mock app that captures posted messages."""
        app = MagicMock()
        app.posted_messages = []
        app.post_message = lambda msg: app.posted_messages.append(msg)
        return app

    @pytest.fixture
    def controller(self, mock_app):
        """Create a controller with mock app."""
        return OrchestrationController(mock_app)

    def test_start_initializes_context(self, controller):
        """start() should initialize context and emit message."""
        controller.start("test-plan", 5)

        assert controller.context.plan_name == "test-plan"
        assert controller.context.total_phases == 5
        assert controller.context.state == UIState.RUNNING

    def test_start_emits_message(self, controller, mock_app):
        """start() should emit OrchestrationStarted message."""
        controller.start("test-plan", 5)

        assert len(mock_app.posted_messages) == 1
        msg = mock_app.posted_messages[0]
        assert isinstance(msg, OrchestrationStarted)
        assert msg.plan_name == "test-plan"
        assert msg.total_phases == 5

    def test_toggle_verbose(self, controller, mock_app):
        """toggle_verbose() should flip state and emit message."""
        assert controller.context.verbose is True  # Default

        result = controller.toggle_verbose()

        assert result is False
        assert controller.context.verbose is False
        # Should emit VerboseToggled and HUDMessageSet
        assert any(isinstance(m, VerboseToggled) for m in mock_app.posted_messages)

    def test_token_accumulation(self, controller):
        """Token stats should accumulate correctly."""
        # First update (no cost - intermediate)
        controller.update_token_stats(100, 50, 0.0, 100, 200_000)
        assert controller.context.total_cost_usd == 0.0

        # Final update (with cost)
        controller.update_token_stats(100, 50, 0.05, 100, 200_000)
        assert controller.context.total_input_tokens == 100
        assert controller.context.total_cost_usd == 0.05

        # Another final update
        controller.update_token_stats(200, 100, 0.10, 200, 200_000)
        assert controller.context.total_input_tokens == 300
        assert controller.context.total_cost_usd == 0.15

    def test_action_queue(self, controller):
        """Action queue should be FIFO."""
        controller.queue_action(UserAction.PAUSE)
        controller.queue_action(UserAction.SKIP)

        assert controller.get_pending_action() == UserAction.PAUSE
        assert controller.get_pending_action() == UserAction.SKIP
        assert controller.get_pending_action() == UserAction.NONE

    def test_set_phase_updates_context(self, controller, mock_app):
        """set_phase() should update context and emit message."""
        mock_phase = Mock()
        mock_phase.id = "phase-1"
        mock_phase.title = "Setup"

        controller.context.total_phases = 3
        controller.set_phase(mock_phase, 1)

        assert controller.context.current_phase == "phase-1"
        assert controller.context.phase_title == "Setup"
        assert controller.context.phase_index == 1

        # Check message
        msg = next(m for m in mock_app.posted_messages if isinstance(m, PhaseChanged))
        assert msg.phase_id == "phase-1"
        assert msg.phase_title == "Setup"
```

### Integration Testing with Pilot

```python
# tests/test_tui_integration.py

import pytest
from textual.pilot import Pilot

from debussy.ui.tui import DebussyTUI
from debussy.ui.controller import OrchestrationController


class TestTUIIntegration:
    """Integration tests using Textual's pilot testing."""

    @pytest.fixture
    async def app(self):
        """Create app with controller."""
        app = DebussyTUI()
        controller = OrchestrationController(app)
        app.set_controller(controller)
        return app

    async def test_phase_change_updates_hud(self, app):
        """PhaseChanged message should update HUD."""
        async with app.run_test() as pilot:
            # Simulate controller emitting phase change
            from debussy.ui.messages import PhaseChanged
            app.post_message(PhaseChanged(
                phase_id="p1",
                phase_title="Setup",
                phase_index=1,
                total_phases=3,
            ))
            await pilot.pause()

            # Verify HUD updated
            header = app.query_one("#hud-header")
            assert "1/3: Setup" in header.phase_info

    async def test_verbose_toggle_key(self, app):
        """Pressing 'v' should toggle verbose via controller."""
        async with app.run_test() as pilot:
            initial = app._controller.context.verbose

            await pilot.press("v")
            await pilot.pause()

            assert app._controller.context.verbose != initial
```

---

## Migration Path

### Step-by-Step Migration

This migration is designed to be **incremental and non-breaking**. Each step can be merged independently.

#### Step 1: Add New Files (Safe)

**PR #1: Add message types and controller skeleton**

1. Create `src/debussy/ui/messages.py` with all message classes
2. Create `src/debussy/ui/controller.py` with skeleton implementation
3. Add unit tests for controller
4. **No changes to existing files**

**Verification:** All existing tests pass, new tests pass.

#### Step 2: Implement Controller Logic (Safe)

**PR #2: Implement controller business logic**

1. Complete `OrchestrationController` implementation
2. Add comprehensive unit tests
3. **No changes to TUI yet**

**Verification:** New tests pass, existing tests pass.

#### Step 3: Dual-Mode Bridge (Safe)

**PR #3: Add controller integration with backward compatibility**

1. Modify `TextualUI` to create and hold controller
2. Add `set_controller()` to `DebussyTUI`
3. Make TUI methods check for controller and delegate if present
4. **Both paths work** - old direct calls and new message-based

```python
# tui.py - Dual-mode bridge
def set_phase(self, phase: Phase, index: int) -> None:
    """Update the current phase (backward compatible)."""
    if self._controller:
        # New path: delegate to controller
        self._controller.set_phase(phase, index)
    else:
        # Old path: direct update (deprecated)
        self.ui_context.current_phase = phase.id
        # ... rest of old code ...
```

**Verification:** All tests pass, manual TUI testing works.

#### Step 4: Add Message Handlers (Safe)

**PR #4: Add TUI message handlers**

1. Add `on_*` handlers for all controller messages
2. Messages work alongside old direct updates
3. Add integration tests with pilot

**Verification:** New handlers work, old path still works.

#### Step 5: Remove Old Code (Breaking for Tests)

**PR #5: Remove deprecated direct update code**

1. Remove `ui_context` from `DebussyTUI`
2. Remove old direct update methods
3. Update any tests that relied on old behavior
4. Controller is now the single source of truth

**Verification:** All tests pass with new architecture.

### Rollback Strategy

Each PR is independently revertable:
- PR #1-2: Pure additions, revert removes new files
- PR #3: Revert removes controller usage, TUI works standalone
- PR #4: Revert removes handlers, falls back to direct updates
- PR #5: Revert restores old code, dual-mode works again

---

## Risk Mitigation

### Identified Risks

| Risk | Impact | Mitigation |
|------|--------|------------|
| Message ordering issues | Medium | Use `call_later()` for thread safety |
| Performance regression | Low | Messages are lightweight, profile if needed |
| Missing message handler | High | Type hints + tests catch missing handlers |
| Controller not set | High | Defensive checks with fallback behavior |
| Circular imports | Medium | Keep messages in separate module |

### Safety Checks

```python
# Defensive controller access
def action_toggle_verbose(self) -> None:
    if self._controller is None:
        logger.warning("Controller not set, verbose toggle ignored")
        return
    self._controller.toggle_verbose()

# Type-safe message handling
def on_phase_changed(self, message: PhaseChanged) -> None:
    """Handle phase change - type checked by Textual."""
    # Textual ensures only PhaseChanged messages call this
```

### Monitoring Points

During rollout, monitor for:
1. **Log messages:** "Controller not set" warnings
2. **HUD not updating:** Missing message handler
3. **Actions not working:** Queue not being processed
4. **Performance:** Slow rendering after message flood

---

## Appendix: Full Controller Implementation

For reference, here is the complete `OrchestrationController` class:

```python
# src/debussy/ui/controller.py
"""Orchestration state controller for the TUI."""

from __future__ import annotations

import time
from collections import deque
from typing import TYPE_CHECKING

from textual.app import App
from textual.message import Message

from debussy.ui.base import UIContext, UIState, UserAction
from debussy.ui.messages import (
    HUDMessageSet,
    LogMessage,
    OrchestrationCompleted,
    OrchestrationStarted,
    PhaseChanged,
    StateChanged,
    TokenStatsUpdated,
    VerboseToggled,
)

if TYPE_CHECKING:
    from debussy.core.models import Phase


class OrchestrationController:
    """Manages orchestration state and emits UI messages.

    This controller owns all orchestration state and business logic.
    The TUI subscribes to messages and renders accordingly.

    Responsibilities:
    - UIContext singleton ownership
    - Action queue management
    - Token usage accumulation
    - State machine transitions
    - Emitting UI update messages
    """

    def __init__(self, app: App) -> None:
        """Initialize the controller.

        Args:
            app: The Textual app to post messages to
        """
        self._app = app
        self.context = UIContext()
        self._action_queue: deque[UserAction] = deque()

    def _post(self, message: Message) -> None:
        """Post a message to the TUI.

        Uses call_from_thread for thread safety when called from workers.
        """
        self._app.post_message(message)

    # =========================================================================
    # Orchestration Lifecycle
    # =========================================================================

    def start(self, plan_name: str, total_phases: int) -> None:
        """Initialize orchestration state.

        Called by the orchestrator when starting a run.
        """
        self.context.plan_name = plan_name
        self.context.total_phases = total_phases
        self.context.start_time = time.time()
        self.context.state = UIState.RUNNING
        self._post(OrchestrationStarted(plan_name, total_phases))

    def stop(self) -> None:
        """Stop the orchestration (no-op, app controls lifecycle)."""
        pass

    def set_phase(self, phase: Phase, index: int) -> None:
        """Update the current phase being executed.

        Args:
            phase: The phase model
            index: 1-based index of the phase
        """
        self.context.current_phase = phase.id
        self.context.phase_title = phase.title
        self.context.phase_index = index
        self.context.start_time = time.time()
        self._post(PhaseChanged(
            phase_id=phase.id,
            phase_title=phase.title,
            phase_index=index,
            total_phases=self.context.total_phases,
        ))

    def set_state(self, state: UIState) -> None:
        """Update the UI state.

        Args:
            state: New state (RUNNING, PAUSED, etc.)
        """
        self.context.state = state
        self._post(StateChanged(state))

    def complete(self, run_id: str, success: bool, message: str) -> None:
        """Signal orchestration completion.

        Args:
            run_id: The run ID
            success: Whether orchestration succeeded
            message: Completion message
        """
        self._post(OrchestrationCompleted(run_id, success, message))

    # =========================================================================
    # Token Statistics
    # =========================================================================

    def update_token_stats(
        self,
        input_tokens: int,
        output_tokens: int,
        cost_usd: float,
        context_tokens: int,
        context_window: int = 200_000,
    ) -> None:
        """Update token usage statistics.

        Per-turn updates show cumulative stats within current session.
        Final result (with cost > 0) adds session totals to run totals.

        Args:
            input_tokens: Input tokens this session
            output_tokens: Output tokens this session
            cost_usd: Cost in USD (>0 only on final result)
            context_tokens: Current context window usage
            context_window: Maximum context window size
        """
        # Update current session stats
        self.context.session_input_tokens = input_tokens
        self.context.session_output_tokens = output_tokens
        self.context.current_context_tokens = context_tokens
        self.context.context_window = context_window

        # Final result has cost - add session totals to run totals
        if cost_usd > 0:
            self.context.total_input_tokens += input_tokens
            self.context.total_output_tokens += output_tokens
            self.context.total_cost_usd += cost_usd

        # Calculate context percentage
        context_pct = 0
        if context_window > 0 and context_tokens > 0:
            context_pct = int((context_tokens / context_window) * 100)

        session_total = input_tokens + output_tokens
        self._post(TokenStatsUpdated(
            session_input_tokens=session_total,
            session_output_tokens=output_tokens,
            total_cost_usd=self.context.total_cost_usd,
            context_pct=context_pct,
        ))

    # =========================================================================
    # User Actions
    # =========================================================================

    def queue_action(self, action: UserAction) -> None:
        """Queue a user action for processing by the orchestrator.

        Args:
            action: The action requested by the user
        """
        self._action_queue.append(action)

        # Emit appropriate feedback message
        feedback_map = {
            UserAction.PAUSE: "Pause requested (after current operation)",
            UserAction.RESUME: "Resume requested",
            UserAction.SKIP: "Skip requested (after current operation)",
            UserAction.QUIT: "Quit requested",
        }
        if action in feedback_map:
            self._post(HUDMessageSet(feedback_map[action]))

    def get_pending_action(self) -> UserAction:
        """Get and remove the next pending user action.

        Called by the orchestrator to check for user input.

        Returns:
            The next action, or UserAction.NONE if queue is empty
        """
        if self._action_queue:
            action = self._action_queue.popleft()
            self.context.last_action = action
            return action
        return UserAction.NONE

    # =========================================================================
    # Verbose Toggle
    # =========================================================================

    def toggle_verbose(self) -> bool:
        """Toggle verbose logging mode.

        Returns:
            New verbose state
        """
        self.context.verbose = not self.context.verbose
        self._post(VerboseToggled(self.context.verbose))
        state_str = "ON" if self.context.verbose else "OFF"
        self._post(HUDMessageSet(f"Verbose: {state_str}"))
        return self.context.verbose

    # =========================================================================
    # Logging
    # =========================================================================

    def log_message(self, message: str) -> None:
        """Log a message (respects verbose setting).

        Args:
            message: Message to log
        """
        self._post(LogMessage(message, raw=False))

    def log_message_raw(self, message: str) -> None:
        """Log a message (ignores verbose setting).

        Args:
            message: Message to log
        """
        self._post(LogMessage(message, raw=True))

    # =========================================================================
    # Status
    # =========================================================================

    def show_status_popup(self, details: dict[str, str]) -> None:
        """Show status details in the log.

        Args:
            details: Key-value pairs to display
        """
        self._post(LogMessage("", raw=True))
        self._post(LogMessage("[bold]Current Status[/bold]", raw=True))
        for key, value in details.items():
            self._post(LogMessage(f"  {key}: {value}", raw=True))
        self._post(LogMessage("", raw=True))

    def confirm(self, message: str) -> bool:
        """Ask for user confirmation (auto-confirms in TUI mode).

        Args:
            message: Confirmation message

        Returns:
            Always True (TUI auto-confirms)
        """
        self._post(LogMessage(f"[yellow]{message}[/yellow] (auto-confirmed)", raw=True))
        return True
```

---

## Summary

This architecture plan provides a clear path to separate UI and business logic in the Debussy TUI:

1. **New `OrchestrationController` class** owns all state and business logic
2. **Message-based protocol** enables clean communication
3. **`DebussyTUI` becomes pure view** - renders and forwards input
4. **Incremental migration path** with rollback capability
5. **Comprehensive testing strategy** enables confident refactoring

The plan prioritizes:
- **Safety:** Each step is independently testable and revertable
- **Clarity:** Clear boundaries and responsibilities
- **Textual Best Practices:** Uses the framework's message system
- **Maintainability:** Future changes isolated to appropriate layers

**Estimated Effort:** 3-5 PRs over 1-2 weeks

**Next Steps:**
1. Review and approve this plan
2. Create issue for each PR
3. Begin with PR #1 (messages + controller skeleton)
