# TaskTracker MVP Phase 1: Data Layer Foundation

**Status:** Pending
**Master Plan:** [TaskTracker MVP - Master Plan](MASTER_PLAN.md)
**Depends On:** None

---

## Process Wrapper (MANDATORY)

- [ ] Project initialization: `npm init -y && npm install mongoose dotenv`
- [ ] Install dev dependencies: `npm install --save-dev jest @types/node`
- [ ] **[IMPLEMENTATION - see Tasks below]**
- [ ] Pre-validation (ALL required):
  ```bash
  # Code quality and testing
  npm run lint --fix
  npm test -- --coverage
  ```
- [ ] Fix loop: repeat pre-validation until clean
- [ ] Write `notes/NOTES_phase1_data_layer.md` (REQUIRED)

## Gates (must pass before completion)

**ALL gates are BLOCKING.**

- lint: 0 errors
- tests: All tests pass
- coverage: >90% coverage on models and repositories
- security: npm audit shows no high severity vulnerabilities

---

## Overview

Build the database foundation using MongoDB and Mongoose. This phase establishes the data models, schemas, basic data access patterns, and validation rules that all subsequent modules will depend on. Includes User and Task models, repository pattern for data access, database connection management, and comprehensive unit and integration tests.

## Dependencies
- Previous phase: None (this is the foundation)
- External: MongoDB (local or MongoDB Atlas)

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| MongoDB installation issues on different OS | Low | Medium | Provide detailed setup instructions for all platforms, use Docker as alternative |
| Schema design changes needed later | Medium | Medium | Design schemas carefully now, document design decisions, plan for migrations |
| Index optimization overlooked | Low | Medium | Benchmark common queries early, add indexes proactively, document query patterns |
| Validation logic duplicated | Medium | Low | Create centralized validation schemas separate from Mongoose, reuse across layers |

---

## Tasks

### 1. Project Setup & Configuration

- [ ] 1.1: Initialize Node.js project with `npm init -y`
- [ ] 1.2: Install core dependencies: `mongoose`, `dotenv`, `jest`
- [ ] 1.3: Create directory structure (`src/models`, `src/repositories`, `src/config`, `src/validation`)
- [ ] 1.4: Create `.env.example` with MongoDB connection strings
- [ ] 1.5: Set up Jest configuration for testing
- [ ] 1.6: Create `src/config/database.js` with Database connection manager class

### 2. User Model & Validation

- [ ] 2.1: Create `src/models/User.js` with Mongoose schema including email, username, passwordHash, timestamps, settings
- [ ] 2.2: Add schema indexes (email unique, username unique)
- [ ] 2.3: Implement `toJSON()` method to remove passwordHash from output
- [ ] 2.4: Add static methods: `findByEmail()`, `findByUsername()`
- [ ] 2.5: Create `src/validation/schemas.js` with user validation schema
- [ ] 2.6: Write unit tests for User model in `tests/models/User.test.js` (>90% coverage)
- [ ] 2.7: Test schema validation, unique constraints, static methods, virtual fields

### 3. Task Model & Validation

- [ ] 3.1: Create `src/models/Task.js` with Mongoose schema including title, description, status, priority, dueDate, userId, tags, timestamps
- [ ] 3.2: Add schema indexes (userId, status, createdAt, compound index on userId+status)
- [ ] 3.3: Implement pre-save middleware to update `updatedAt` timestamp
- [ ] 3.4: Implement pre-save middleware to set `completedAt` when status changes to 'done'
- [ ] 3.5: Add methods: `markComplete()`, `isOverdue()`
- [ ] 3.6: Add static methods: `findByUser()`, `findByStatus()`, `searchTasks()`
- [ ] 3.7: Add virtual field: `daysUntilDue`
- [ ] 3.8: Add task validation schema to `src/validation/schemas.js`
- [ ] 3.9: Write unit tests for Task model in `tests/models/Task.test.js` (>90% coverage)
- [ ] 3.10: Test schema validation, middleware hooks, methods, statics, virtuals, search functionality

### 4. Repository Pattern Implementation

- [ ] 4.1: Create `src/repositories/UserRepository.js` with methods: `create()`, `findById()`, `findByEmail()`, `findByUsername()`, `update()`, `delete()`, `exists()`
- [ ] 4.2: Create `src/repositories/TaskRepository.js` with methods: `create()`, `findById()`, `findByUser()`, `findByStatus()`, `update()`, `delete()`, `search()`, `getStatsByUser()`, `bulkUpdate()`
- [ ] 4.3: Implement error handling in all repository methods (validation, not found, duplicate key)
- [ ] 4.4: Add filtering and sorting support to `findByUser()` method
- [ ] 4.5: Write integration tests for UserRepository in `tests/repositories/UserRepository.test.js`
- [ ] 4.6: Write integration tests for TaskRepository in `tests/repositories/TaskRepository.test.js`
- [ ] 4.7: Test with isolated test database, cleanup after execution

### 5. Database Connection & Configuration

- [ ] 5.1: Implement `Database.connect(uri)` method with retry logic
- [ ] 5.2: Implement `Database.disconnect()` graceful shutdown
- [ ] 5.3: Add connection pooling configuration (min: 5, max: 10)
- [ ] 5.4: Add socket timeout (30s) and server selection timeout (5s)
- [ ] 5.5: Implement event handlers: connection success, disconnection, connection errors
- [ ] 5.6: Write unit tests for Database connection manager
- [ ] 5.7: Test successful connection, failed connection, reconnection logic, connection pooling

### 6. Testing & Validation

- [ ] 6.1: Create test utilities in `tests/setup.js` for test database initialization and cleanup
- [ ] 6.2: Write unit tests achieving >90% coverage for all models
- [ ] 6.3: Write integration tests for all repositories with test database
- [ ] 6.4: Add seed data script in `scripts/seed.js` for development
- [ ] 6.5: Test index creation and query performance with indexes
- [ ] 6.6: Run `npm test` and verify all tests pass
- [ ] 6.7: Generate coverage report, identify any gaps, add tests as needed

### 7. Documentation & Quality

- [ ] 7.1: Create `README.md` with database setup instructions for all platforms
- [ ] 7.2: Document User model schema with field descriptions
- [ ] 7.3: Document Task model schema with field descriptions
- [ ] 7.4: Document repository methods with input/output signatures
- [ ] 7.5: Create example usage file showing how to use models and repositories
- [ ] 7.6: Run ESLint and fix any linting errors
- [ ] 7.7: Create `.env.example` file with all required variables

---

## Files to Create/Modify

| File | Action | Purpose |
|------|--------|---------|
| `src/config/database.js` | Create | Database connection manager with pooling and event handling |
| `src/models/User.js` | Create | Mongoose User schema with validation and methods |
| `src/models/Task.js` | Create | Mongoose Task schema with validation and middleware |
| `src/repositories/UserRepository.js` | Create | Data access layer for User operations |
| `src/repositories/TaskRepository.js` | Create | Data access layer for Task operations |
| `src/validation/schemas.js` | Create | Centralized validation schemas for all models |
| `tests/models/User.test.js` | Create | Unit tests for User model |
| `tests/models/Task.test.js` | Create | Unit tests for Task model |
| `tests/repositories/UserRepository.test.js` | Create | Integration tests for UserRepository |
| `tests/repositories/TaskRepository.test.js` | Create | Integration tests for TaskRepository |
| `tests/setup.js` | Create | Test utilities and database setup/teardown |
| `scripts/seed.js` | Create | Development seed data script |
| `README.md` | Create | Setup and usage documentation |
| `.env.example` | Create | Environment variable template |
| `package.json` | Modify | Add test scripts and dependencies |

## Patterns to Follow

| Pattern | Reference | Usage |
|---------|-----------|-------|
| Repository Pattern | `src/repositories/` | Abstract database operations, enable easy testing with mocks |
| Mongoose Middleware | `src/models/Task.js` | Auto-update timestamps, set derived fields like completedAt |
| Validation Separation | `src/validation/schemas.js` | Keep validation logic separate from models, reuse across layers |
| Error Handling | Repository methods | Validate input, handle not-found errors, handle duplicate key errors |
| Test Database | `tests/setup.js` | Use separate test database, clean up after each test |

## Test Strategy

- [ ] Unit tests for User model (schema validation, methods, statics, virtuals)
- [ ] Unit tests for Task model (schema validation, middleware, methods, statics, virtuals)
- [ ] Integration tests for UserRepository (CRUD operations with test database)
- [ ] Integration tests for TaskRepository (CRUD, search, filtering with test database)
- [ ] Database connection tests (success, failure, reconnection, pooling)
- [ ] Index optimization tests (verify indexes are created and used)
- [ ] Edge case tests (empty results, invalid IDs, data constraints)

## Acceptance Criteria

**ALL must pass:**

- [ ] All User model tests pass (>90% coverage)
- [ ] All Task model tests pass (>90% coverage)
- [ ] All repository tests pass (>85% coverage)
- [ ] Database connection tests pass
- [ ] ESLint passes with 0 errors
- [ ] npm audit shows no high severity vulnerabilities
- [ ] README documentation is complete and clear
- [ ] Example usage demonstrates all major functionality
- [ ] Seeds script successfully populates test data

## Rollback Plan

If Phase 1 encounters critical issues:

1. **Failed tests:** Review error messages, fix implementation, rerun tests
2. **Schema incompatibility:** Delete test database and recreate with `npm run seed`, restart development
3. **Index issues:** Drop all indexes with `db.collection.dropIndex()`, verify schema indexes are correct, restart MongoDB
4. **Complete reset:** 
   - Delete local MongoDB data directory or MongoDB Atlas cluster
   - Delete `node_modules` and reinstall with `npm install`
   - Reinitialize database and seed with fresh data

---

## Implementation Notes

This phase creates the foundation that all subsequent phases depend on. Key architectural decisions:

1. **Repository Pattern:** Used to abstract database operations and enable easy mocking in tests. Simplifies switching databases later if needed.

2. **Validation Separation:** Schemas are defined separately from Mongoose for clarity and to enable reuse across the API validation layer (Phase 3).

3. **Middleware for Timestamps:** Pre-save hooks automatically maintain `updatedAt` and `completedAt` fields, reducing error-prone manual updates.

4. **Indexes Early:** Indexes are created on frequently queried fields (userId, status, timestamps) to ensure good performance from day one.

5. **Test Database:** Tests use an isolated test database to avoid affecting development data and enable parallel test execution.