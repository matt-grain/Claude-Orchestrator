# TaskTracker MVP Phase 3: Task API Module

**Status:** Pending
**Master Plan:** [TaskTracker MVP - Master Plan](MASTER_PLAN.md)
**Depends On:** [Phase 2: Authentication Module](tasktracker-phase-2.md)

---

## Process Wrapper (MANDATORY)
- [ ] Read previous notes: `notes/NOTES_phase_2_auth.md`
- [ ] Verify Phases 1 and 2 are complete and all gates passing
- [ ] **[IMPLEMENTATION - see Tasks below]**
- [ ] Pre-validation (ALL required):
  ```bash
  npm run lint --fix
  npm run type-check
  npm test
  ```
- [ ] Fix loop: repeat pre-validation until clean
- [ ] Write `notes/NOTES_phase_3_api.md` (REQUIRED)

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
- tests: All tests pass (>85% coverage)
  ```bash
  command: npm test -- --coverage
  ```
- security: No high severity issues
  ```bash
  command: npm audit
  ```
- performance: API endpoints respond within 100ms
  ```bash
  command: npm run test:performance
  ```

---

## Overview

Build the REST API for task management operations. This phase provides endpoints for creating, reading, updating, and deleting tasks, with filtering, search, pagination, and statistics. The API must be secure, performant, and well-tested as it's the backbone for Phase 4 (UI).

## Dependencies
- Previous phase: [Phase 2: Authentication Module](tasktracker-phase-2.md) - requires auth middleware and services
- External: None new (uses existing dependencies)

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| SQL injection via search/filter | Low | Critical | Use Mongoose query builder (not raw queries), validate and sanitize input |
| Unauthorized access to other users' tasks | Medium | High | Implement ownership checks (ensureTaskOwnership middleware), test thoroughly |
| API performance degrades with large datasets | Medium | Medium | Implement pagination early, add database indexes, benchmark queries, cache stats |
| Circular dependency or query N+1 problems | Medium | Medium | Use Mongoose lean() for read-only queries, implement query batching |
| Bulk operations cause data inconsistency | Low | Medium | Use transactions for bulk updates, test concurrent modifications |

---

## Tasks

### 1. Express Application Setup
- [ ] 1.1: Create main Express app in `src/app.js` with middleware stack
- [ ] 1.2: Configure CORS with frontend URL allowlist
- [ ] 1.3: Configure security headers with helmet middleware
- [ ] 1.4: Configure request logging with morgan
- [ ] 1.5: Configure body parsing for JSON and URL-encoded data
- [ ] 1.6: Implement health check endpoint (`/health`)
- [ ] 1.7: Implement 404 handler and error handler

### 2. Task Controller Implementation
- [ ] 2.1: Create TaskController in `src/controllers/TaskController.js`
- [ ] 2.2: Implement create endpoint (validate, add userId, create via repository)
- [ ] 2.3: Implement list endpoint (extract filters, paginate, return with metadata)
- [ ] 2.4: Implement getById endpoint (find task, verify ownership, return)
- [ ] 2.5: Implement update endpoint (find, verify ownership, validate, update)
- [ ] 2.6: Implement delete endpoint (find, verify ownership, delete)
- [ ] 2.7: Implement search endpoint (search title/description, apply filters)
- [ ] 2.8: Implement getStats endpoint (count by status, count by priority, overdue count)
- [ ] 2.9: Implement bulkUpdate endpoint (verify ownership for all, update multiple)
- [ ] 2.10: Implement markComplete endpoint (set status to done, timestamp)

### 3. Task Routes and Validation
- [ ] 3.1: Create task routes in `src/routes/tasks.js`
- [ ] 3.2: Protect all task routes with authentication middleware
- [ ] 3.3: Create validateTask middleware for request validation
- [ ] 3.4: Create validateTaskUpdate middleware for partial updates
- [ ] 3.5: Create ensureTaskOwnership middleware for authorization checks
- [ ] 3.6: Apply validation and authorization middleware to routes
- [ ] 3.7: Document all query parameters and filtering options

### 4. Filtering, Search, and Pagination
- [ ] 4.1: Create pagination utility in `src/utils/pagination.js`
- [ ] 4.2: Implement filter logic for status, priority, tags, overdue
- [ ] 4.3: Implement sort logic with configurable fields and order
- [ ] 4.4: Implement search across title and description (case-insensitive)
- [ ] 4.5: Implement pagination metadata (page, limit, total, totalPages, hasNext, hasPrev)
- [ ] 4.6: Test all filtering and pagination combinations
- [ ] 4.7: Optimize queries with indexes and lean() for read operations

### 5. Testing and Integration
- [ ] 5.1: Write unit tests for TaskController methods
- [ ] 5.2: Write integration tests for all endpoints using supertest
- [ ] 5.3: Test CRUD operations with valid and invalid data
- [ ] 5.4: Test filtering with various parameter combinations
- [ ] 5.5: Test pagination edge cases (page 0, limit 0, total < limit)
- [ ] 5.6: Test search functionality (case sensitivity, special characters)
- [ ] 5.7: Test authorization (own tasks, other users' tasks, unauthenticated)
- [ ] 5.8: Test error responses (404, 403, 400, validation errors)
- [ ] 5.9: Test performance (endpoints respond < 100ms with 1000+ tasks)
- [ ] 5.10: Achieve >85% test coverage for Phase 3

### 6. Documentation and Response Formatting
- [ ] 6.1: Create API documentation in `docs/api.md` with all endpoints
- [ ] 6.2: Document request/response schemas for each endpoint
- [ ] 6.3: Document error responses and status codes
- [ ] 6.4: Create Postman collection for manual testing
- [ ] 6.5: Implement consistent response format (success, data, message, pagination)
- [ ] 6.6: Test all responses match documented schema

---

## Files to Create/Modify

| File | Action | Purpose |
|------|--------|---------|
| `src/app.js` | Create | Express application setup with middleware |
| `src/controllers/TaskController.js` | Create | All task operation handlers |
| `src/routes/tasks.js` | Create | Task API route definitions |
| `src/middleware/validation.js` | Modify | Add task validation functions |
| `src/middleware/taskAuth.js` | Create | Task ownership verification middleware |
| `src/utils/pagination.js` | Create | Pagination utilities and metadata |
| `tests/api/tasks.test.js` | Create | Integration tests for all task endpoints |
| `tests/controllers/TaskController.test.js` | Create | Unit tests for task controller |
| `docs/api.md` | Create | Complete API documentation |
| `postman-collection.json` | Create | Postman collection for testing |
| `src/server.js` | Modify | Import app and start server |

## Patterns to Follow

| Pattern | Reference | Usage |
|---------|-----------|-------|
| Controller Pattern | TaskController with method per endpoint | Handle HTTP logic, delegate to repositories |
| Middleware Composition | Protect routes with auth + validation + authorization | Separate concerns, reuse middleware |
| Query Building | Pagination utility, filter logic | Construct flexible queries safely |
| Error Handling | Consistent error responses with statusCode | Unified error format across API |
| Test Fixtures | Seed data, test user/task creation helpers | Consistent test setup, reduce duplication |

## Test Strategy

- [ ] Unit tests for TaskController (all methods, error paths, validation)
- [ ] Integration tests for POST /tasks (valid creation, missing fields, unauthenticated)
- [ ] Integration tests for GET /tasks (list, filtering, pagination, sorting)
- [ ] Integration tests for GET /tasks/:id (found, not found, wrong user)
- [ ] Integration tests for PUT /tasks/:id (valid update, partial update, wrong user)
- [ ] Integration tests for DELETE /tasks/:id (delete, not found, wrong user)
- [ ] Integration tests for GET /tasks/search (search by title, description, empty results)
- [ ] Integration tests for GET /tasks/stats (accurate counts, empty user)
- [ ] Integration tests for PATCH /tasks/bulk (multiple updates, verification)
- [ ] Integration tests for POST /tasks/:id/complete (mark done, verify timestamp)
- [ ] Performance tests (100 tasks list in < 100ms, search in < 100ms)
- [ ] Authorization tests (cannot access other users' tasks, proper error codes)

## Acceptance Criteria

**ALL must pass:**

- [ ] All tasks completed as specified
- [ ] All gates passing (lint, type-check, tests, security, performance)
- [ ] Test coverage exceeds 85% for Phase 3
- [ ] All CRUD operations work correctly
- [ ] Filtering and sorting return expected results
- [ ] Search finds tasks correctly (case-insensitive)
- [ ] Pagination works with various limit/page combinations
- [ ] Users can only access their own tasks (authorization verified)
- [ ] API endpoints respond within 100ms with 1000+ tasks
- [ ] Error messages are consistent and helpful
- [ ] All responses match documented schema
- [ ] Postman collection works for manual testing

## Rollback Plan

If Phase 3 fails validation:
1. Reset to Phase 2 completion: `git reset --hard <phase_2_complete_commit>`
2. Review failed API tests in test output
3. Check performance benchmarks - if slow, review indexes and query optimization
4. Reset test database: `npm run db:reset`
5. If authorization tests fail, verify ensureTaskOwnership middleware is applied to all routes
6. If filtering/pagination tests fail, verify query building logic in controller
7. If response format tests fail, ensure all endpoints return consistent structure
8. Fix identified issues and re-run all gates
9. Manually test API with Postman collection before declaring phase complete

---

## Implementation Notes

{To be filled during implementation}