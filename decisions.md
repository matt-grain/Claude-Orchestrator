# Architecture Decision Records

## 2025-12 — Docker Sandboxing for Untrusted Code Execution

**Status:** accepted

**Context:** Debussy orchestrates Claude Code as a subprocess to execute arbitrary AI-driven coding tasks
against a user's project. Claude Code, when running, can invoke shell commands, install packages, write
files, and make network requests. Running this directly on the host machine exposes the host filesystem,
credentials, and network to whatever Claude decides to do, with no containment boundary.

**Decision:** Each Claude worker session runs inside a dedicated Docker container (`debussy-sandbox:latest`)
built from `src/debussy/docker/Dockerfile.sandbox`. The container:
- Runs Claude Code as a non-root user (`claude`, UID 1001) based on Anthropic's official devcontainer.
- Mounts only the target project directory as `/workspace`, not the host home or `.config`.
- Applies an `iptables`/`ipset` firewall (via `init-firewall.sh`) that defaults to DROP, allowing only
  the Anthropic API, GitHub, npm, PyPI, and local network — blocking arbitrary internet access.
- Installs the `debussy` and `claude-ltm` CLI tools inside the container so Claude can signal completion
  (`/debussy-done`) and save learnings without host access.

**Alternatives considered:**
- **Local subprocess execution** (no container): Simpler to set up but gives Claude unrestricted access
  to the host filesystem, environment variables, and all network endpoints. Unacceptable for any production
  or multi-user scenario.
- **VM-based isolation** (e.g., QEMU/Firecracker): Stronger isolation but far heavier startup latency and
  more complex volume sharing. Docker volume mounts already create friction on Windows (requiring
  `PRAGMA synchronous=FULL` in SQLite to handle grpcfuse flush delays); VMs would worsen this further.
- **Process-level sandboxing** (seccomp/AppArmor without Docker): Requires root configuration per host and
  is not portable across developer machines or CI environments.

**Consequences:**
- Docker must be installed and running on the orchestrator host; the sandbox image must be pre-built.
- Volume sync latency on Windows with Docker Desktop (grpcfuse) can cause SQLite writes inside the
  container to be delayed on the host — mitigated by `PRAGMA synchronous=FULL` in `StateManager`.
- The firewall whitelist (`init-firewall.sh`) must be maintained when Claude Code's upstream endpoints
  change (e.g., new Statsig/Sentry hosts).
- The `ClaudeRunner` in `runners/claude.py` gracefully falls back to local execution if Docker is
  unavailable (`_is_sandbox_image_available()`), preserving developer ergonomics on machines without Docker.

---

## 2025-12 — Textual TUI over Simple Rich Output

**Status:** accepted

**Context:** Orchestration runs can span many minutes or hours across multiple phases, each producing a
continuous stream of Claude output. A plain sequential print-to-terminal approach makes it impossible to
simultaneously show a persistent status header (current phase, elapsed time, token usage) and a scrollable
log of Claude's output without the two interleaving and corrupting the display. Users also need in-session
controls (pause, kill, toggle verbosity) without stopping the process.

**Decision:** The UI layer uses [Textual](https://textual.textualize.io/) (`src/debussy/ui/tui.py`), which
provides a proper retained-mode terminal UI with:
- A fixed HUD header that updates in real-time (elapsed timer via `reactive`, current phase, token stats,
  active agent).
- A scrollable `RichLog` panel for Claude's streaming output, independent of the HUD.
- Keyboard bindings for pause/resume, kill, and verbose toggle without blocking the orchestration worker.
- Modal confirmation dialogs (e.g., `ResumeConfirmScreen`) for destructive actions.
- A `@work` worker running the orchestration coroutine, keeping the event loop unblocked.

Orchestration logic runs as a Textual worker (`@work`), posting typed messages (`LogMessage`,
`PhaseChanged`, `TokenStatsUpdated`, etc.) to the app, which handles them on the UI thread.

**Alternatives considered:**
- **Plain `rich.Live` + `rich.Layout`**: Supports a split layout but requires manual refresh management
  and cannot handle keyboard bindings or modal screens without significant custom code. Rich's `Live`
  context manager is designed for short-lived displays, not multi-hour orchestration sessions.
- **Simple `print()` / `logging` to stdout**: Zero setup, but provides no persistent HUD, no keyboard
  control, and no way to separate status from log output. Adequate for CI but not for interactive use.
- **curses directly**: Full control but requires reimplementing widgets, focus management, and async
  integration from scratch.

**Consequences:**
- Textual is an additional runtime dependency. It is well-maintained and already in the Python ecosystem
  via PyPI, but adds ~2 MB to the install.
- The clean separation between UI messages (`ui/messages.py`) and orchestration logic means the
  orchestrator can be driven without the TUI (e.g., in CI mode) by substituting a no-op message sink.
- Textual's async model integrates naturally with the existing `asyncio`-based runner stack.

---

## 2025-12 — SQLite for Run State Persistence

**Status:** accepted

**Context:** Multi-phase orchestration runs can be interrupted (context limit reached, user kill, crash).
The system must be able to resume a run from the last completed phase without re-executing already-done
work. This requires durable, queryable state that survives process restarts. The state includes: run
metadata, per-phase execution records (status, attempt count, PID, log path), gate results, completion
signals, and a progress log.

**Decision:** All run state is persisted in a local SQLite database managed by `StateManager`
(`src/debussy/core/state.py`). The schema uses five normalised tables (`runs`, `phase_executions`,
`gate_results`, `completion_signals`, `progress_log`) with foreign key relationships. SQLite is accessed
synchronously via the stdlib `sqlite3` module with a context-manager-per-operation pattern. Connections
use `PRAGMA synchronous=FULL` to guarantee flush visibility across Docker volume mounts on Windows.
Resumability is implemented via `find_resumable_run()`, which queries for the most recent incomplete run
for a given plan path.

**Alternatives considered:**
- **In-memory state only**: Simple but lost on any crash or restart. Unacceptable given that Claude
  sessions can hit context limits mid-phase and need to restart, which requires knowing what was already
  completed.
- **JSON/pickle files**: Easy to implement but non-queryable. Queries like "find the most recent
  incomplete run for this plan" would require loading and scanning all files. Concurrent access (e.g.,
  the `debussy done` CLI signal written from inside Docker) would require file-locking.
- **PostgreSQL or other server DB**: Overkill for a single-user local tool; requires a running server
  process, connection configuration, and network access from inside Docker. SQLite is embedded and
  requires no daemon.
- **Redis**: Appropriate for ephemeral state but not for durable, structured, queryable run history.

**Consequences:**
- The database file lives alongside the project (configurable path), making it easy to inspect with any
  SQLite browser.
- `PRAGMA synchronous=FULL` is required for Docker volume mount compatibility on Windows (grpcfuse may
  buffer writes); this has a small performance cost but is correct for correctness over throughput.
- The synchronous `sqlite3` access pattern is intentional: state writes are infrequent (phase
  transitions), so async overhead would add complexity with negligible benefit. All heavy I/O (Claude
  subprocess, gate commands) is already async.
- `StateManager` has no global singleton — it is instantiated with an explicit `db_path`, making it
  trivially testable with a temporary directory.

---

## 2025-12 — Compliance Verification as an Independent Gate Pattern

**Status:** accepted

**Context:** Claude, like any LLM, can claim in its completion report that it ran all required steps,
invoked all required agents, and passed all quality gates — without actually having done so. Trusting
Claude's self-assessment would allow low-quality or incomplete phase outputs to silently propagate
through the pipeline.

**Decision:** After each phase completes, `ComplianceChecker` (`src/debussy/core/compliance.py`)
independently re-verifies the phase output before the orchestrator proceeds. Verification is structured
as four independent checks:
1. **Gates re-execution**: All phase gates (linters, type checkers, tests defined in the plan) are
   re-run by `GateRunner` regardless of what Claude claims — the code comment explicitly states
   "NEVER trust Claude's claim".
2. **Notes file verification**: The required notes file is read and checked for mandatory sections
   (`## Summary`, `## Key Decisions`, `## Files Modified`, and optionally `## Learnings` when LTM is
   enabled).
3. **Agent invocation evidence**: The session log is scanned with regex patterns to find evidence that
   required sub-agents were actually launched via the Task tool, not just claimed in the report.
4. **Required step completion**: Named steps are verified against both the completion report and the
   session log.

Issues are classified by severity (`critical`, `high`, `low`), and a `RemediationStrategy` is derived
(full retry, targeted fix, or warn-and-accept), decoupling detection from remediation policy.

**Alternatives considered:**
- **Trust Claude's completion report**: Zero implementation cost, but breaks the fundamental principle
  that orchestrated AI must be verifiable. A single hallucinated "gates passed" claim would ship broken
  code.
- **Re-run only gates, trust the rest**: Partial verification. Notes and agent invocation checks catch
  a different class of failures (structural incompleteness vs. code quality) and are cheap to run.
- **Human review gate between every phase**: Correct but defeats the purpose of autonomous orchestration
  for long multi-phase plans. Compliance verification enables unattended runs with confidence.
- **Single monolithic validator script**: Would couple gate execution, log parsing, and notes checking
  into one black box. The current design separates `GateRunner` (pure command execution) from
  `ComplianceChecker` (policy enforcement), allowing each to be tested and evolved independently.

**Consequences:**
- Every phase takes slightly longer due to re-running gates (linters, type checks). This is acceptable
  because gate execution is already bounded by the per-gate timeout in `GateRunner` (default 300 s).
- The compliance layer operates on the session log string, which means it must be fully captured before
  verification runs. This drives the design of the streaming parser to accumulate the full log.
- False negatives are possible for agent invocation checks (regex heuristics on log text), which is why
  the severity for "claimed but not evidenced" is `high` rather than `critical`, triggering a targeted
  fix rather than a full retry.
