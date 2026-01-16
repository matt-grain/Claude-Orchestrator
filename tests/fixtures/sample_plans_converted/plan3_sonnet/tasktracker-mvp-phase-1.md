# TaskTracker MVP Phase 1: Data Layer Foundation

**Status:** Pending
**Master Plan:** [tasktracker-mvp-MASTER_PLAN.md](tasktracker-mvp-MASTER_PLAN.md)
**Depends On:** None (foundational phase)

---

## Process Wrapper (MANDATORY)
- [ ] Read previous notes: N/A (first phase)
- [ ] **[IMPLEMENTATION - see Tasks below]**
- [ ] Pre-validation (ALL required):
  ```bash
  # Code quality
  npm run lint --fix
  npm run test
  ```
- [ ] Fix loop: repeat pre-validation until clean
- [ ] Write `notes/NOTES_tasktracker_phase_1.md` (REQUIRED)

## Gates (must pass before completion)

**ALL gates are BLOCKING.**

- lint: `npm run lint` - 0 errors
- tests: `npm test` - All tests pass (>90% coverage for models and repositories)
- security: `npm audit` - No high severity issues

---

## Overview

Build the database foundation using MongoDB and Mongoose. This phase establishes the data models, schemas, and basic data access patterns that all other modules will depend on. We'll create User and Task schemas with proper validation, indexes, and a repository pattern for data access abstraction.

## Dependencies
- Previous phase: N/A (foundational)
- External: MongoDB (local or Atlas), Node.js, npm

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Schema changes break compatibility later | Medium | High | Version schemas, use migrations, comprehensive tests |
| Database connection failures | Low | Medium | Implement retry logic, connection pooling, proper error handling |
| Index performance issues with large datasets | Low | Medium | Add indexes early, monitor query performance, use explain() |
| Validation rules too strict or too loose | Medium | Low | Test edge cases thoroughly, iterate based on feedback |

---

## Tasks

### 1. Project Initialization
- [ ] 1.1: Initialize Node.js project with `npm init -y`
- [ ] 1.2: Install dependencies: `mongoose`, `dotenv`
- [ ] 1.3: Install dev dependencies: `jest`, `@types/node`, `eslint`
- [ ] 1.4: Set up MongoDB (local installation or MongoDB Atlas account)
- [ ] 1.5: Create `.env.example` with configuration template
- [ ] 1.6: Configure ESLint and Jest

### 2. Database Connection Manager
- [ ] 2.1: Create `src/config/database.js` with Database class
- [ ] 2.2: Implement `connect(uri)` method with connection pooling
- [ ] 2.3: Implement `disconnect()` method for graceful shutdown
- [ ] 2.4: Add connection event handlers (connected, disconnected, error)
- [ ] 2.5: Configure connection options (pooling, timeouts, auto-reconnect)
- [ ] 2.6: Write connection tests in `tests/config/database.test.js`

### 3. User Schema & Model
- [ ] 3.1: Create `src/models/User.js` with Mongoose schema
- [ ] 3.2: Define fields: email, username, passwordHash, createdAt, settings
- [ ] 3.3: Add validation rules (required, unique, email format, length)
- [ ] 3.4: Create indexes for email and username
- [ ] 3.5: Implement `toJSON()` method to remove passwordHash from output
- [ ] 3.6: Add static methods: `findByEmail()`, `findByUsername()`
- [ ] 3.7: Write unit tests in `tests/models/User.test.js`

### 4. Task Schema & Model
- [ ] 4.1: Create `src/models/Task.js` with Mongoose schema
- [ ] 4.2: Define fields: title, description, status, priority, dueDate, userId, tags, timestamps
- [ ] 4.3: Add validation rules and enums (status, priority)
- [ ] 4.4: Create indexes: userId, status, createdAt, compound (userId, status)
- [ ] 4.5: Implement pre-save middleware for updatedAt and completedAt
- [ ] 4.6: Add methods: `markComplete()`, `isOverdue()`
- [ ] 4.7: Add statics: `findByUser()`, `findByStatus()`, `searchTasks()`
- [ ] 4.8: Add virtual: `daysUntilDue`
- [ ] 4.9: Write unit tests in `tests/models/Task.test.js`

### 5. Repository Pattern
- [ ] 5.1: Create `src/repositories/UserRepository.js`
- [ ] 5.2: Implement UserRepository methods: create, findById, findByEmail, findByUsername, update, delete, exists
- [ ] 5.3: Create `src/repositories/TaskRepository.js`
- [ ] 5.4: Implement TaskRepository methods: create, findById, findByUser, update, delete, search, getStatsByUser, bulkUpdate
- [ ] 5.5: Write integration tests in `tests/repositories/UserRepository.test.js`
- [ ] 5.6: Write integration tests in `tests/repositories/TaskRepository.test.js`

### 6. Validation Schemas
- [ ] 6.1: Create `src/validation/schemas.js`
- [ ] 6.2: Define `createUserSchema` with email, username, password rules
- [ ] 6.3: Define `createTaskSchema` with title, description, status, priority, dueDate rules
- [ ] 6.4: Add validation helper functions for common patterns
- [ ] 6.5: Write validation tests

### 7. Seed Data & Documentation
- [ ] 7.1: Create `scripts/seed.js` with example data
- [ ] 7.2: Write `README.md` with database setup instructions
- [ ] 7.3: Document schema designs with field descriptions
- [ ] 7.4: Document repository usage with examples
- [ ] 7.5: Create database diagram or ERD

---

## Files to Create/Modify

| File | Action | Purpose |
|------|--------|---------|
| `package.json` | Create | Node.js project configuration |
| `.env.example` | Create | Environment variable template |
| `src/config/database.js` | Create | Database connection manager |
| `src/models/User.js` | Create | User Mongoose schema and model |
| `src/models/Task.js` | Create | Task Mongoose schema and model |
| `src/repositories/UserRepository.js` | Create | User data access layer |
| `src/repositories/TaskRepository.js` | Create | Task data access layer |
| `src/validation/schemas.js` | Create | Validation schemas |
| `scripts/seed.js` | Create | Seed data script |
| `tests/config/database.test.js` | Create | Database connection tests |
| `tests/models/User.test.js` | Create | User model unit tests |
| `tests/models/Task.test.js` | Create | Task model unit tests |
| `tests/repositories/UserRepository.test.js` | Create | UserRepository integration tests |
| `tests/repositories/TaskRepository.test.js` | Create | TaskRepository integration tests |
| `README.md` | Create | Database setup and usage documentation |

## Patterns to Follow

| Pattern | Reference | Usage |
|---------|-----------|-------|
| Repository Pattern | `src/repositories/` | Abstract database operations behind clean interfaces |
| Schema Validation | Mongoose docs | Use Mongoose built-in validation with custom validators |
| Async/Await | ES2017 standard | Use async/await for all database operations |
| Error Handling | Try/catch blocks | Wrap all DB operations in try/catch, throw meaningful errors |
| Test Isolation | Jest beforeEach/afterEach | Use test database, clean up after each test |

## Test Strategy

- [ ] Unit tests for User model: schema validation, unique constraints, email validation, toJSON, static methods
- [ ] Unit tests for Task model: required fields, enum validation, timestamps, middleware, virtuals, search functionality
- [ ] Integration tests for UserRepository: CRUD operations, edge cases, error handling
- [ ] Integration tests for TaskRepository: CRUD operations, search, filters, getStatsByUser
- [ ] Database connection tests: valid URI succeeds, invalid URI fails, reconnection works, pooling limits
- [ ] Use isolated test database (separate from dev database)
- [ ] Clean up test data after each test run

## Validation

- Use `python-task-validator` to verify code quality and architecture (despite being a Node.js project, the validator can check general code patterns and structure)

## Acceptance Criteria

**ALL must pass:**

- [ ] All tasks completed
- [ ] All gates passing (lint, tests, security)
- [ ] Unit tests achieve >90% coverage for models
- [ ] Integration tests pass for all repositories
- [ ] Database connection manager handles errors gracefully
- [ ] Schema validation prevents invalid data
- [ ] Indexes created for frequently queried fields
- [ ] Documentation complete (README, schema docs, examples)
- [ ] No hardcoded credentials or secrets
- [ ] Seed data script works correctly

## Rollback Plan

Since this is the first phase with no production system:
1. Delete the `src/` and `tests/` directories
2. Remove `node_modules/` and `package-lock.json`
3. Drop the test database: `mongo tasktracker_test --eval "db.dropDatabase()"`
4. Revert to initial commit if using git

No data loss risk as this is the foundational phase.

---

## Implementation Notes

### MongoDB Connection String Format
```
mongodb://localhost:27017/tasktracker_dev (local)
mongodb+srv://user:pass@cluster.mongodb.net/tasktracker (Atlas)
```

### Key Environment Variables
```
MONGODB_URI=mongodb://localhost:27017/tasktracker_dev
MONGODB_TEST_URI=mongodb://localhost:27017/tasktracker_test
NODE_ENV=development
```

### Repository Pattern Benefits
- Abstracts database operations from business logic
- Easier to mock in tests
- Centralized query logic
- Can switch databases with minimal code changes
- Consistent error handling

### Index Strategy
- `email` and `username` on User (unique indexes for lookups)
- `userId` on Task (efficient user task queries)
- `status` on Task (for filtering)
- `createdAt` on Task (for sorting)
- Compound `(userId, status)` on Task (most common query pattern)