# DevContainer Sandbox Implementation Plan

> **Note:** This document is historical and may not reflect the current state of the project.

**Version:** 1.1
**Date:** 2026-01-14
**Status:** Prototype

---

## Overview

This plan describes how to add Docker-based sandboxing to Debussy using a custom Docker image based on Anthropic's official DevContainer. The goal is to provide secure, fully autonomous (YOLO mode) execution across all platforms.

### Key Design Decision

**Debussy stays on the host, only Claude sessions run in containers.**

This is intentional:
- Debussy orchestrates and manages state - it needs host access for SQLite, logs, TUI
- Only the untrusted Claude CLI sessions are sandboxed
- Each phase spawns a fresh container - true ephemeral isolation
- Simpler than running everything in Docker

### Why DevContainer?

| Requirement | DevContainer |
|-------------|--------------|
| Cross-platform | Linux, macOS, Windows (Docker Desktop) |
| YOLO mode support | Designed for `--dangerously-skip-permissions` |
| Official support | Based on Anthropic's reference implementation |
| Network security | Built-in firewall with allowlist |
| User effort | Just needs Docker installed |

---

## Architecture

### Current Flow (No Sandbox)

```
Host System
    │
    └─► Debussy Orchestrator (Python)
            │
            └─► asyncio.create_subprocess_exec("claude", ...)
                    │
                    └─► Claude CLI (FULL HOST ACCESS - DANGEROUS)
```

### New Flow (DevContainer Sandbox)

```
Host System
    │
    └─► Debussy Orchestrator (Python) ◄── Stays on host, manages state
            │
            └─► asyncio.create_subprocess_exec("docker", "run", ...)
                    │
                    ▼
            ┌─────────────────────────────────────┐
            │  Docker Container (isolated)         │
            │  ┌─────────────────────────────────┐ │
            │  │ Claude CLI (sandboxed)          │ │
            │  │ - Can only access /workspace    │ │
            │  │ - Network firewall active       │ │
            │  │ - YOLO mode enabled             │ │
            │  └─────────────────────────────────┘ │
            │  /workspace ◄── mounted from host    │
            └─────────────────────────────────────┘
```

---

## Implementation Steps

### Step 1: Add Configuration Option

**File:** `src/debussy/config.py`

```python
from typing import Literal

class Config(BaseModel):
    # ... existing fields ...

    sandbox_mode: Literal["none", "devcontainer"] = Field(
        default="none",
        description="Sandboxing mode for Claude sessions"
    )
```

**Config file example:**
```yaml
# .debussy/config.yaml
sandbox_mode: devcontainer  # or "none" for current behavior
```

---

### Step 2: Add Docker Availability Check

**File:** `src/debussy/runners/claude.py`

```python
import shutil
import subprocess

def _is_docker_available() -> bool:
    """Check if Docker is installed and the daemon is running."""
    if not shutil.which("docker"):
        return False
    try:
        result = subprocess.run(
            ["docker", "info"],
            capture_output=True,
            timeout=10
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, OSError):
        return False
```

---

### Step 3: Modify ClaudeRunner Command Building

**File:** `src/debussy/runners/claude.py`

Add a method to build the command based on sandbox mode:

```python
# Image name constant
SANDBOX_IMAGE = "debussy-sandbox:latest"

def _build_claude_command(self, prompt: str) -> list[str]:
    """Build Claude CLI command, optionally wrapped in Docker."""

    base_args = [
        "--print",
        "--verbose",
        "--output-format", "stream-json",
        "--model", self.model,
        "-p", prompt,
    ]

    if self.config.sandbox_mode == "devcontainer":
        # Custom image with Python/uv tooling
        # Build with: docker build -t debussy-sandbox:latest -f docker/Dockerfile.sandbox docker/
        project_path = _normalize_path_for_docker(self.project_root)

        return [
            "docker", "run",
            "--rm",                          # Remove container after exit
            "-i",                            # Interactive (for stdin streaming)
            "-v", f"{project_path}:/workspace:rw",  # Mount project
            "-w", "/workspace",              # Set working directory
            # Pass API key
            "-e", f"ANTHROPIC_API_KEY={os.environ.get('ANTHROPIC_API_KEY', '')}",
            # Network capabilities for firewall (optional, for init-firewall.sh)
            "--cap-add=NET_ADMIN",
            "--cap-add=NET_RAW",
            SANDBOX_IMAGE,
            # Note: ENTRYPOINT is "claude", so we just pass args
            "--dangerously-skip-permissions",
            *base_args,
        ]
    else:
        # Current behavior - direct execution (with warning shown at startup)
        return [
            self.claude_command,
            "--dangerously-skip-permissions",
            *base_args,
        ]
```

---

### Step 4: Update execute_phase Method

**File:** `src/debussy/runners/claude.py`

Modify the existing `execute_phase` to use the new command builder:

```python
async def execute_phase(self, phase: Phase, ...) -> ExecutionResult:
    prompt = self._build_prompt(phase, ...)

    # Validate sandbox mode at runtime
    if self.config.sandbox_mode == "devcontainer":
        if not _is_docker_available():
            raise RuntimeError(
                "sandbox_mode is 'devcontainer' but Docker is not available. "
                "Install Docker Desktop or set sandbox_mode: none"
            )

    cmd = self._build_claude_command(prompt)

    # Rest of existing implementation...
    process = await asyncio.create_subprocess_exec(
        cmd[0],
        *cmd[1:],
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        **create_kwargs,
    )
```

---

### Step 5: Add CLI Flags and Commands

**File:** `src/debussy/cli.py`

```python
@click.option(
    "--sandbox/--no-sandbox",
    default=None,
    help="Run Claude in Docker sandbox (requires Docker)"
)
@click.option(
    "--accept-risks",
    is_flag=True,
    default=False,
    help="Skip security warning when running without sandbox (for CI/scripts)"
)
def run(sandbox: bool | None, accept_risks: bool, ...):
    # Load config
    config = load_config(...)

    # CLI flag overrides config file
    if sandbox is not None:
        config.sandbox_mode = "devcontainer" if sandbox else "none"

    # Pass accept_risks to orchestrator
    ...


@cli.group()
def sandbox():
    """Manage Docker sandbox for secure execution."""
    pass


@sandbox.command("build")
def sandbox_build():
    """Build the debussy-sandbox Docker image."""
    import subprocess

    dockerfile = Path(__file__).parent.parent.parent / "docker" / "Dockerfile.sandbox"
    context = dockerfile.parent

    click.echo("Building debussy-sandbox image...")
    result = subprocess.run(
        ["docker", "build", "-t", "debussy-sandbox:latest", "-f", str(dockerfile), str(context)],
        check=False
    )

    if result.returncode == 0:
        click.echo("✓ Image built successfully")
    else:
        click.echo("✗ Build failed", err=True)
        raise SystemExit(1)


@sandbox.command("status")
def sandbox_status():
    """Check if Docker and sandbox image are available."""
    # Check Docker
    # Check image exists
    # Report status
    ...
```

---

### Step 6: Handle Windows Path Translation

Docker on Windows needs special handling for volume mounts:

```python
def _normalize_path_for_docker(path: Path) -> str:
    """Convert Windows path to Docker-compatible format."""
    import platform

    if platform.system() == "Windows":
        # Convert C:\Projects\foo to /c/Projects/foo (Git Bash style)
        # Or use //c/Projects/foo for some Docker versions
        path_str = str(path.resolve())
        if len(path_str) >= 2 and path_str[1] == ':':
            drive = path_str[0].lower()
            rest = path_str[2:].replace('\\', '/')
            return f"/{drive}{rest}"
    return str(path)
```

---

## Testing Plan

### Unit Tests

1. **Config parsing:** Verify `sandbox_mode` is read from config
2. **Command building:** Test Docker command construction
3. **Path normalization:** Test Windows path conversion
4. **Docker check:** Mock `docker info` responses

### Integration Tests

1. **Docker available:** Full execution with Docker
2. **Docker unavailable:** Graceful error message
3. **Volume mounting:** Verify project files are accessible in container
4. **Output streaming:** Verify stream-json output works through Docker

### Manual Testing Checklist

- [ ] Test on Windows with Docker Desktop
- [ ] Test on macOS with Docker Desktop
- [ ] Test on Linux with Docker
- [ ] Verify TUI works correctly with Docker execution
- [ ] Verify Claude can read/write project files
- [ ] Verify network firewall blocks unauthorized hosts
- [ ] Test with missing Docker (graceful error)

---

## Docker Image

### Custom Image: debussy-sandbox

We build a custom image based on Anthropic's DevContainer reference, adding Python/uv for Debussy's quality gates.

**Source:** https://github.com/anthropics/claude-code/tree/main/.devcontainer

**Location:** `docker/Dockerfile.sandbox`

```dockerfile
# Based on Anthropic's official DevContainer
# https://github.com/anthropics/claude-code/tree/main/.devcontainer

FROM node:20-slim

# Build args
ARG CLAUDE_VERSION=latest
ARG TZ=UTC

# System dependencies (from Anthropic's Dockerfile)
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    curl \
    ca-certificates \
    iptables \
    ipset \
    dnsutils \
    jq \
    sudo \
    # Python tooling for Debussy quality gates
    python3 \
    python3-pip \
    && rm -rf /var/lib/apt/lists/*

# Install uv for fast Python package management
RUN curl -LsSf https://astral.sh/uv/install.sh | sh

# Create non-root user
RUN useradd -m -s /bin/bash -u 1000 claude \
    && mkdir -p /workspace \
    && chown claude:claude /workspace

# Install Claude Code globally
RUN npm install -g @anthropic-ai/claude-code@${CLAUDE_VERSION}

# Copy firewall init script (from Anthropic's reference)
COPY init-firewall.sh /usr/local/bin/init-firewall.sh
RUN chmod +x /usr/local/bin/init-firewall.sh \
    && echo "claude ALL=(ALL) NOPASSWD: /usr/local/bin/init-firewall.sh" >> /etc/sudoers

# Switch to non-root user
USER claude
WORKDIR /workspace

# Add uv to PATH
ENV PATH="/home/claude/.cargo/bin:${PATH}"

ENTRYPOINT ["claude"]
```

### Firewall Script

Copy `init-firewall.sh` from Anthropic's reference:
- Allowlists: GitHub, npm, Anthropic API, Sentry, VS Code marketplace
- Blocks all other outbound connections
- Allows DNS (port 53) and SSH (port 22)

### Build Command

```bash
# Build the image
docker build -t debussy-sandbox:latest -f docker/Dockerfile.sandbox docker/

# Or with specific Claude version
docker build -t debussy-sandbox:latest \
  --build-arg CLAUDE_VERSION=1.0.0 \
  -f docker/Dockerfile.sandbox docker/
```

### Why Custom vs Pre-built?

| Approach | Pros | Cons |
|----------|------|------|
| `docker/sandbox-templates:claude-code` | No build step | No Python/uv, can't customize |
| Custom `debussy-sandbox` | Has uv, firewall, customizable | Requires initial build |

**Decision:** Custom image - we need Python tooling for quality gates (ruff, pyright, pytest).

---

## Configuration Examples

### Enable Sandbox (config.yaml)

```yaml
# .debussy/config.yaml
model: opus
timeout: 1800
sandbox_mode: devcontainer
```

### Enable via CLI

```bash
# One-time sandbox run
debussy run --sandbox

# Disable sandbox for this run
debussy run --no-sandbox
```

### Environment Variable (Future)

```bash
DEBUSSY_SANDBOX_MODE=devcontainer debussy run
```

---

## Startup Warning (No Sandbox Mode)

When `sandbox_mode: none` (default), display a prominent warning requiring confirmation:

### TUI Warning Screen

```
┌─────────────────────────────────────────────────────────────────────┐
│                                                                     │
│  ⚠️  SECURITY WARNING                                               │
│                                                                     │
│  You are running Debussy WITHOUT sandboxing.                        │
│                                                                     │
│  Claude Code will have FULL ACCESS to:                              │
│    • Your entire file system (read/write/delete)                    │
│    • Network connections (any host)                                 │
│    • Command execution (any command)                                │
│                                                                     │
│  This is equivalent to giving a stranger SSH access to your         │
│  machine. Only proceed if you trust the master plan source.         │
│                                                                     │
│  To enable sandboxing:                                              │
│    1. Install Docker Desktop                                        │
│    2. Run: debussy run --sandbox                                    │
│    3. Or set sandbox_mode: devcontainer in config.yaml              │
│                                                                     │
│  [I understand the risks, continue] [Cancel and enable sandbox]     │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### Implementation

**File:** `src/debussy/tui/tui.py`

```python
class SecurityWarningScreen(ModalScreen):
    """Warning screen shown when sandbox is disabled."""

    BINDINGS = [
        ("y", "accept", "Continue"),
        ("n", "cancel", "Cancel"),
    ]

    def compose(self) -> ComposeResult:
        yield Static(WARNING_TEXT, id="warning-text")
        yield Button("I understand the risks, continue", id="accept", variant="error")
        yield Button("Cancel and enable sandbox", id="cancel", variant="primary")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "accept":
            self.dismiss(True)
        else:
            self.dismiss(False)
```

**File:** `src/debussy/orchestrator.py`

```python
async def run(self, ...):
    if self.config.sandbox_mode == "none":
        # Show warning and require confirmation
        confirmed = await self.ui.show_security_warning()
        if not confirmed:
            self.ui.log("Cancelled. Enable sandbox with --sandbox flag.")
            return
```

### CLI Non-Interactive Mode

For `--non-interactive` mode, require explicit `--accept-risks` flag:

```bash
# This will fail with error
debussy run --non-interactive

# This will proceed with warning in logs
debussy run --non-interactive --accept-risks
```

---

## Error Handling

### Docker Not Installed

```
Error: sandbox_mode is 'devcontainer' but Docker is not available.

To fix:
  1. Install Docker Desktop from https://docker.com/products/docker-desktop
  2. Or disable sandboxing: debussy run --no-sandbox --accept-risks
```

### Docker Daemon Not Running

```
Error: Docker daemon is not running.

To fix:
  1. Start Docker Desktop
  2. Or disable sandboxing: debussy run --no-sandbox --accept-risks
```

### Image Not Built

```
Error: Docker image 'debussy-sandbox:latest' not found.

To fix:
  1. Build the image: debussy sandbox build
  2. Or run: docker build -t debussy-sandbox:latest -f docker/Dockerfile.sandbox docker/
```

---

## Security Considerations

### What DevContainer Protects Against

- File system access outside `/workspace`
- Network access to non-allowlisted hosts
- Process escape to host system
- Persistent changes outside project directory

### What DevContainer Does NOT Protect Against

- Malicious actions within the project directory
- Exfiltration via allowlisted hosts (GitHub, npm, Anthropic API)
- Reading ANTHROPIC_API_KEY passed to container
- Actions permitted by `--dangerously-skip-permissions`

### Recommendation

> Only use DevContainer sandboxing with **trusted repositories**. The sandbox limits blast radius but cannot prevent all attacks from malicious code.

---

## Rollout Plan

### Phase 1: Prototype

1. Implement basic `sandbox_mode: devcontainer` support
2. Test on all platforms
3. Document setup requirements

### Phase 2: Stabilization

1. Add graceful error handling
2. Add `--sandbox` CLI flag
3. Update README with security guidance

### Phase 3: Default (Future)

Consider making `sandbox_mode: devcontainer` the default once:
- Docker Desktop adoption is high enough
- User feedback confirms UX is acceptable
- No major issues reported

---

## Files to Create/Modify

### New Files

| File | Purpose |
|------|---------|
| `docker/Dockerfile.sandbox` | Custom sandbox image with Python/uv |
| `docker/init-firewall.sh` | Network firewall script (from Anthropic) |
| `src/debussy/tui/screens/security_warning.py` | Security warning modal screen |

### Modified Files

| File | Changes |
|------|---------|
| `src/debussy/config.py` | Add `sandbox_mode` field |
| `src/debussy/runners/claude.py` | Add Docker command wrapping, path normalization |
| `src/debussy/cli.py` | Add `--sandbox`, `--accept-risks` flags, `sandbox build/status` commands |
| `src/debussy/orchestrator.py` | Show security warning before run |
| `src/debussy/tui/tui.py` | Add `show_security_warning()` method |
| `tests/test_claude_runner.py` | Add sandbox mode tests |
| `tests/test_security_warning.py` | Test warning screen behavior |
| `README.md` | Document sandbox mode, security guidance |

---

## Resolved Questions

1. **Which Docker image?** Custom `debussy-sandbox:latest` based on Anthropic's DevContainer, with uv added for Python tooling
2. **Default behavior?** `sandbox_mode: none` with mandatory security warning + confirmation dialog
3. **Image caching?** Docker handles caching - first build takes ~2-3 min, subsequent runs instant
4. **TTY handling?** Use `-i` flag for stdin streaming, no `-t` needed for non-interactive JSON output

---

## References

- [Claude Code DevContainer Docs](https://code.claude.com/docs/en/devcontainer)
- [Docker Sandbox Templates](https://docs.docker.com/ai/sandboxes/claude-code/)
- [Anthropic Sandboxing Blog](https://www.anthropic.com/engineering/claude-code-sandboxing)
- [SANDBOXING_REPORT.md](./SANDBOXING_REPORT.md)
