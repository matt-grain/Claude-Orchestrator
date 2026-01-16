"""Test script to run quality evaluation and show the report."""

import tempfile
from pathlib import Path
from unittest.mock import patch

from debussy.converters import PlanConverter
from debussy.converters.plan_converter import PlanConverter as PlanConverterClass
from debussy.converters.quality import ConversionQualityEvaluator
from debussy.core.auditor import PlanAuditor
from debussy.templates import TEMPLATES_DIR

# Mock Claude output (same as in tests)
MOCK_CLAUDE_OUTPUT = """
---FILE: MASTER_PLAN.md---
# TaskTracker Application - Master Plan

**Created:** 2024-01-15
**Status:** Draft

---

## Overview

TaskTracker is a web-based task management application with user authentication, RESTful API, and React frontend.

## Goals

1. **User Management** - Secure user registration and authentication
2. **Task Management** - Full CRUD operations for tasks
3. **Modern UI** - Responsive React-based dashboard

## Phases

| Phase | Title | Focus | Risk | Status |
|-------|-------|-------|------|--------|
| 1 | [Database Setup](phase-1-database.md) | Database schema and models | Low | Pending |
| 2 | [Backend API](phase-2-backend.md) | REST API development | Medium | Pending |
| 3 | [Frontend](phase-3-frontend.md) | React dashboard | Medium | Pending |

## Success Metrics

| Metric | Current | Phase 1 | Phase 2 | Phase 3 |
|--------|---------|---------|---------|---------|
| Test Coverage | 0% | 80% | 85% | 90% |
| API Endpoints | 0 | 2 | 10 | 10 |

## Dependencies

```
Phase 1 --> Phase 2 --> Phase 3
```

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Schema changes | Low | Medium | Migration scripts |
| API performance | Medium | Medium | Caching layer |

## Out of Scope

- Mobile native apps
- Real-time WebSocket features

## Review Checkpoints

- After Phase 1: Database migrations work
- After Phase 2: All API tests pass
- After Phase 3: UI renders correctly
---END FILE---

---FILE: phase-1-database.md---
# TaskTracker Phase 1: Database Setup

**Status:** Pending
**Master Plan:** [MASTER_PLAN.md](MASTER_PLAN.md)
**Depends On:** N/A

---

## Process Wrapper (MANDATORY)
- [ ] Read previous notes: N/A (first phase)
- [ ] **[IMPLEMENTATION - see Tasks below]**
- [ ] Pre-validation (ALL required):
  ```bash
  uv run ruff format . && uv run ruff check --fix .
  uv run pyright src/
  uv run pytest tests/ -v
  ```
- [ ] Fix loop: repeat pre-validation until clean
- [ ] Write `notes/NOTES_tasktracker_phase_1.md` (REQUIRED)

## Gates (must pass before completion)

**ALL gates are BLOCKING.**

- lint: 0 errors (command: `uv run ruff check .`)
- type-check: 0 errors (command: `uv run pyright src/`)
- tests: All tests pass (command: `uv run pytest tests/`)

---

## Overview

Set up PostgreSQL database with SQLAlchemy models for users and tasks.

## Tasks

### 1. Database Configuration
- [ ] 1.1: Set up PostgreSQL connection
- [ ] 1.2: Configure SQLAlchemy ORM

### 2. Model Implementation
- [ ] 2.1: Create User model with password hashing
- [ ] 2.2: Create Task model with relationships
- [ ] 2.3: Create migration scripts

## Validation

- Use `python-task-validator` to verify model code quality

## Acceptance Criteria

- [ ] All models defined with appropriate fields
- [ ] Relationships correctly established
- [ ] Migration scripts run without errors
---END FILE---

---FILE: phase-2-backend.md---
# TaskTracker Phase 2: Backend API

**Status:** Pending
**Master Plan:** [MASTER_PLAN.md](MASTER_PLAN.md)
**Depends On:** [Phase 1](phase-1-database.md)

---

## Process Wrapper (MANDATORY)
- [ ] Read previous notes: `notes/NOTES_tasktracker_phase_1.md`
- [ ] **[IMPLEMENTATION - see Tasks below]**
- [ ] Pre-validation (ALL required):
  ```bash
  uv run ruff format . && uv run ruff check --fix .
  uv run pyright src/
  uv run pytest tests/ -v
  ```
- [ ] Fix loop: repeat pre-validation until clean
- [ ] Write `notes/NOTES_tasktracker_phase_2.md` (REQUIRED)

## Gates (must pass before completion)

**ALL gates are BLOCKING.**

- lint: 0 errors (command: `uv run ruff check .`)
- type-check: 0 errors (command: `uv run pyright src/`)
- tests: All tests pass (command: `uv run pytest tests/`)
- security: No high severity issues (command: `uv run bandit -r src/`)

---

## Overview

Develop Flask REST API with authentication and CRUD endpoints.

## Tasks

### 1. Authentication
- [ ] 1.1: Implement user registration endpoint
- [ ] 1.2: Implement login with JWT tokens
- [ ] 1.3: Create auth middleware

### 2. Task Endpoints
- [ ] 2.1: Create task endpoint
- [ ] 2.2: Read task(s) endpoint
- [ ] 2.3: Update task endpoint
- [ ] 2.4: Delete task endpoint

## Validation

- Use `python-task-validator` to verify API implementation

## Acceptance Criteria

- [ ] All endpoints return appropriate status codes
- [ ] Authentication blocks unauthorized access
- [ ] Input validation catches malformed requests
---END FILE---

---FILE: phase-3-frontend.md---
# TaskTracker Phase 3: Frontend Dashboard

**Status:** Pending
**Master Plan:** [MASTER_PLAN.md](MASTER_PLAN.md)
**Depends On:** [Phase 2](phase-2-backend.md)

---

## Process Wrapper (MANDATORY)
- [ ] Read previous notes: `notes/NOTES_tasktracker_phase_2.md`
- [ ] **[IMPLEMENTATION - see Tasks below]**
- [ ] Pre-validation (ALL required):
  ```bash
  npm run lint --fix
  npm run type-check
  npm test
  ```
- [ ] Fix loop: repeat pre-validation until clean
- [ ] Write `notes/NOTES_tasktracker_phase_3.md` (REQUIRED)

## Gates (must pass before completion)

**ALL gates are BLOCKING.**

- lint: 0 errors (command: `npm run lint`)
- type-check: 0 errors (command: `npm run type-check`)
- tests: All tests pass (command: `npm test`)

---

## Overview

Build React frontend with authentication and task management UI.

## Tasks

### 1. Authentication UI
- [ ] 1.1: Login form component
- [ ] 1.2: Registration form component
- [ ] 1.3: Auth state management

### 2. Dashboard
- [ ] 2.1: Task list component
- [ ] 2.2: Task creation form
- [ ] 2.3: Task editing modal
- [ ] 2.4: Filtering and sorting

## Acceptance Criteria

- [ ] UI responsive on mobile and desktop
- [ ] All API calls handle errors gracefully
- [ ] Auth state persists across sessions
---END FILE---
"""


def main():
    # Set up paths
    sample_plans_dir = Path("tests/fixtures/sample_plans")
    plan1_dir = sample_plans_dir / "plan1_tasktracker_basic"

    # Create temp output directory
    with tempfile.TemporaryDirectory() as tmp_dir:
        output_dir = Path(tmp_dir) / "converted"
        output_dir.mkdir()

        # Mock the Claude call
        with patch.object(PlanConverterClass, "_run_claude", return_value=MOCK_CLAUDE_OUTPUT):
            auditor = PlanAuditor()
            converter = PlanConverter(auditor=auditor, templates_dir=TEMPLATES_DIR)

            # Run conversion
            result = converter.convert(
                source_plan=plan1_dir / "master_plan.md",
                output_dir=output_dir,
            )

            print("CONVERSION RESULT")
            print("=" * 60)
            print(f"Success: {result.success}")
            print(f"Iterations: {result.iterations}")
            print(f"Files created: {result.files_created}")
            if result.warnings:
                print(f"Warnings: {result.warnings}")
            print()

            # Run audit on converted plan
            audit_result = auditor.audit(output_dir / "MASTER_PLAN.md")
            print("AUDIT RESULT")
            print("=" * 60)
            print(f"Passed: {audit_result.passed}")
            print(f"Errors: {audit_result.summary.errors}")
            print(f"Warnings: {audit_result.summary.warnings}")
            print(f"Phases found: {audit_result.summary.phases_found}")
            print(f"Phases valid: {audit_result.summary.phases_valid}")
            print(f"Gates total: {audit_result.summary.gates_total}")
            print()

            # Run quality evaluation
            evaluator = ConversionQualityEvaluator(
                source_dir=plan1_dir,
                output_dir=output_dir,
            )
            quality = evaluator.evaluate(audit_result=audit_result)

            print("QUALITY EVALUATION")
            print("=" * 60)
            print(quality.summary())


if __name__ == "__main__":
    main()
