# TaskTracker MVP Phase 1: Data Layer Module

**Status:** Pending
**Master Plan:** [TaskTracker MVP - Master Plan](MASTER_PLAN.md)
**Depends On:** None

---

## Process Wrapper (MANDATORY)
- [ ] Verify Node.js and MongoDB installation
- [ ] **[IMPLEMENTATION - see Tasks below]**
- [ ] Pre-validation (ALL required):
  ```bash
  npm run lint --fix
  npm run type-check
  npm test
  ```
- [ ] Fix loop: repeat pre-validation until clean
- [ ] Write `notes/NOTES_phase_1_data.md` (REQUIRED)

## Gates (must pass before completion)

**ALL gates are BLOCKING.**

- lint: 0 errors
  ```bash
  command: npm run lint
  ```
- type-check: 0 errors
  ```bash
  command: npm run type-check
  ```
- tests: All tests pass (>90% coverage)
  ```bash
  command: npm test -- --coverage
  ```
- security: No high severity issues
  ```bash
  command: npm audit
  ```

---

## Overview

Build the database foundation using MongoDB and Mongoose. This phase establishes the data models, schemas, and basic data access patterns that all other modules will depend on. The foundation must be solid, tested, and documented as it directly impacts the architecture of subsequent phases.

## Dependencies
- Previous phase: None (this is the foundation)
- External: Node.js (v18+), MongoDB (local or Atlas), npm

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| MongoDB connection issues in test environment | Low | Medium | Set up test database before implementation, use connection retries, document setup steps |
| Mongoose schema design becomes complex | Medium | Medium | Review schema design with team before implementation, keep models focused and simple |
| Index performance issues not caught early | Low | Medium | Add indexes as specified, write benchmarking tests for common queries |
| Repository pattern not familiar to team | Medium | Low | Document repository pattern with examples, provide reference implementations |

---

## Tasks

### 1. Project Setup and Configuration
- [ ] 1.1: Initialize Node.js project with npm and package.json
- [ ] 1.2: Install Mongoose, dotenv, and development dependencies (Jest, ESLint, TypeScript)
- [ ] 1.3: Create MongoDB connection manager in `src/config/database.js`
- [ ] 1.4: Set up environment variables (.env.example with MONGODB_URI, MONGODB_TEST_URI)
- [ ] 1.5: Create database initialization script for development and testing

### 2. User Model and Validation
- [ ] 2.1: Create User schema with Mongoose in `src/models/User.js`
- [ ] 2.2: Define User fields (email, username, passwordHash, createdAt, settings)
- [ ] 2.3: Add unique indexes on email and username
- [ ] 2.4: Implement instance methods (toJSON to remove sensitive fields)
- [ ] 2.5: Implement static methods (findByEmail, findByUsername)
- [ ] 2.6: Write comprehensive unit tests for User model (>90% coverage)

### 3. Task Model and Validation
- [ ] 3.1: Create Task schema with Mongoose in `src/models/Task.js`
- [ ] 3.2: Define Task fields (title, description, status, priority, dueDate, userId, tags, timestamps)
- [ ] 3.3: Add indexes (userId, status, createdAt, compound userId+status)
- [ ] 3.4: Implement middleware hooks (pre-save for updatedAt and completedAt)
- [ ] 3.5: Implement instance methods (markComplete, isOverdue)
- [ ] 3.6: Implement static methods (findByUser, findByStatus, searchTasks)
- [ ] 3.7: Implement virtual properties (daysUntilDue)
- [ ] 3.8: Write comprehensive unit tests for Task model (>90% coverage)

### 4. Repository Pattern Implementation
- [ ] 4.1: Create UserRepository class in `src/repositories/UserRepository.js` with CRUD methods
- [ ] 4.2: Create TaskRepository class in `src/repositories/TaskRepository.js` with CRUD and search methods
- [ ] 4.3: Implement bulkUpdate method for tasks
- [ ] 4.4: Implement getStatsByUser for task statistics
- [ ] 4.5: Write integration tests for repositories using isolated test database (>90% coverage)

### 5. Validation Schemas
- [ ] 5.1: Create validation schemas in `src/validation/schemas.js` separate from Mongoose
- [ ] 5.2: Define createUserSchema with email, username, password validation rules
- [ ] 5.3: Define createTaskSchema with title, description, status, priority validation rules
- [ ] 5.4: Write unit tests for validation schemas

### 6. Testing and Documentation
- [ ] 6.1: Write unit tests for all models in `tests/models/`
- [ ] 6.2: Write integration tests for all repositories in `tests/repositories/`
- [ ] 6.3: Write database connection tests in `tests/config/`
- [ ] 6.4: Achieve >90% test coverage for Phase 1
- [ ] 6.5: Create database setup documentation in README
- [ ] 6.6: Document schema structure and relationships
- [ ] 6.7: Create example seed data script for development

---

## Files to Create/Modify

| File | Action | Purpose |
|------|--------|---------|
| `src/config/database.js` | Create | MongoDB connection manager with pooling and event handlers |
| `src/models/User.js` | Create | User schema with validation, indexes, and methods |
| `src/models/Task.js` | Create | Task schema with complex validation and middleware |
| `src/repositories/UserRepository.js` | Create | Data access layer for User operations |
| `src/repositories/TaskRepository.js` | Create | Data access layer for Task operations with advanced queries |
| `src/validation/schemas.js` | Create | Standalone validation schemas |
| `tests/models/User.test.js` | Create | Unit tests for User model |
| `tests/models/Task.test.js` | Create | Unit tests for Task model |
| `tests/repositories/UserRepository.test.js` | Create | Integration tests for UserRepository |
| `tests/repositories/TaskRepository.test.js` | Create | Integration tests for TaskRepository |
| `.env.example` | Create | Environment variable template |
| `package.json` | Modify | Add Mongoose, Jest, and other dependencies |

## Patterns to Follow

| Pattern | Reference | Usage |
|---------|-----------|-------|
| Repository Pattern | src/repositories/ | Abstract database operations for easier testing and switching databases |
| Mongoose Middleware | Task.js pre-save hooks | Update timestamps and calculated fields automatically |
| Static Methods | User.findByEmail() | Provide query shortcuts at model level |
| Validation Separation | src/validation/schemas.js | Keep validation logic independent of Mongoose |
| Test Database Isolation | tests/config/setup.js | Use separate test database to avoid affecting development data |

## Test Strategy

- [ ] Unit tests for User model (all methods, validation, uniqueness)
- [ ] Unit tests for Task model (all methods, virtual properties, middleware)
- [ ] Integration tests for UserRepository (CRUD against test database)
- [ ] Integration tests for TaskRepository (CRUD, search, filtering against test database)
- [ ] Database connection tests (valid/invalid URI, reconnection, pooling)
- [ ] Validation tests (schema enforcement, required fields, type checking)
- [ ] Index efficiency tests (common query patterns execute correctly)

## Acceptance Criteria

**ALL must pass:**

- [ ] All tasks completed as specified
- [ ] All gates passing (lint, type-check, tests, security)
- [ ] Test coverage exceeds 90% for all models and repositories
- [ ] No security vulnerabilities in dependencies
- [ ] Database schema is well-documented
- [ ] Repository pattern is correctly implemented and testable
- [ ] Example seed data script works without errors
- [ ] Mongoose connections handle errors gracefully

## Rollback Plan

If Phase 1 fails validation:
1. Reset to last known good commit: `git reset --hard <last_working_commit>`
2. Verify test database is clean: `npm run db:reset`
3. Review failed tests and error logs in `test-results.log`
4. Fix identified issues and re-run pre-validation gates
5. If schema changes were made, manually drop test database and reinitialize: `db.dropDatabase()`

---

## Implementation Notes

{To be filled during implementation}