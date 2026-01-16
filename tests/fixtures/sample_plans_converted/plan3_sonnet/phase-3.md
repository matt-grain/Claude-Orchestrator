# TaskTracker MVP Phase 3: Task API Endpoints

**Status:** Pending
**Master Plan:** [TaskTracker MVP - Master Plan](MASTER_PLAN.md)
**Depends On:** [Phase 2: Authentication System](phase-2.md)

---

## Process Wrapper (MANDATORY)

- [ ] Review previous notes: `notes/NOTES_phase2_authentication.md`
- [ ] Install API dependencies: `npm install cors helmet morgan`
- [ ] **[IMPLEMENTATION - see Tasks below]**
- [ ] Pre-validation (ALL required):
  ```bash
  # Code quality and testing
  npm run lint --fix
  npm test -- --coverage
  npm audit
  ```
- [ ] Fix loop: repeat pre-validation until clean
- [ ] Write `notes/NOTES_phase3_task_api.md` (REQUIRED)

## Gates (must pass before completion)

**ALL gates are BLOCKING.**

- lint: 0 errors
- tests: All API tests pass
- coverage: >85% coverage on controllers and routes
- security: npm audit shows no high severity vulnerabilities, CORS properly configured
- performance: API endpoints respond in <100ms

---

## Overview

Build the REST API for task management operations. This phase provides endpoints for creating, reading, updating, and deleting tasks, with filtering, search, pagination, and statistics. Includes task controller with business logic, route definitions, authorization checks to prevent cross-user access, pagination helpers, comprehensive integration tests, and API documentation.

## Dependencies
- Previous phase: Phase 2 (Authentication System with authenticate middleware)
- Previous phase: Phase 1 (Data Layer with TaskRepository)
- External: cors, helmet, morgan libraries

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| API performance degrades with large datasets | Medium | Medium | Add pagination early, implement database indexes, load test before completion |
| Authorization bypass vulnerability | Low | High | Verify task ownership on every operation, verify user is authenticated |
| Invalid query parameters crash API | Low | Medium | Validate and sanitize all query parameters, set defaults, max values |
| Race conditions in concurrent updates | Low | Medium | Let database handle atomicity, don't implement manual locking in Phase 3 |
| Rate limiting not implemented | Low | Low | Out of scope for MVP, document for production deployment (Phase 5) |

---

## Tasks

### 1. Express Application Setup

- [ ] 1.1: Create `src/app.js` with Express application factory
- [ ] 1.2: Install and configure security middleware: helmet for HTTP headers
- [ ] 1.3: Install and configure CORS middleware with frontend URL
- [ ] 1.4: Install and configure Morgan for request logging
- [ ] 1.5: Configure body parsing middleware for JSON requests
- [ ] 1.6: Add health check endpoint `GET /health`
- [ ] 1.7: Add 404 handler for unmatched routes
- [ ] 1.8: Attach global error handler middleware
- [ ] 1.9: Create `src/server.js` to start Express server
- [ ] 1.10: Configure server to listen on port 3000 with graceful shutdown

### 2. Task Controller Implementation

- [ ] 2.1: Create `src/controllers/TaskController.js` class
- [ ] 2.2: Implement `create(req, res)` endpoint handler
  - [ ] Validate input using validation middleware
  - [ ] Extract task data from request body
  - [ ] Add userId from authenticated user
  - [ ] Create task via TaskRepository
  - [ ] Return created task with 201 status
- [ ] 2.3: Implement `list(req, res)` endpoint handler
  - [ ] Extract query parameters (status, priority, tags, search, sort, order, page, limit)
  - [ ] Build filter object from parameters
  - [ ] Apply sorting and pagination
  - [ ] Return tasks with pagination metadata
- [ ] 2.4: Implement `getById(req, res)` endpoint handler
  - [ ] Extract task ID from params
  - [ ] Find task in database
  - [ ] Verify task belongs to authenticated user
  - [ ] Return task or 404
- [ ] 2.5: Implement `update(req, res)` endpoint handler
  - [ ] Extract task ID and update data
  - [ ] Find task and verify ownership
  - [ ] Validate update data
  - [ ] Update task in database
  - [ ] Return updated task
- [ ] 2.6: Implement `delete(req, res)` endpoint handler
  - [ ] Extract task ID
  - [ ] Find task and verify ownership
  - [ ] Delete from database
  - [ ] Return 204 No Content
- [ ] 2.7: Implement `search(req, res)` endpoint handler
  - [ ] Extract search query parameter
  - [ ] Search title and description
  - [ ] Apply user filter
  - [ ] Return matching tasks
- [ ] 2.8: Implement `getStats(req, res)` endpoint handler
  - [ ] Get authenticated user
  - [ ] Calculate counts by status (todo, in_progress, done)
  - [ ] Calculate counts by priority (low, medium, high)
  - [ ] Calculate overdue task count
  - [ ] Return statistics object
- [ ] 2.9: Implement `bulkUpdate(req, res)` endpoint handler
  - [ ] Extract task IDs and updates
  - [ ] Verify all tasks belong to user
  - [ ] Update all tasks in database
  - [ ] Return updated count
- [ ] 2.10: Implement `markComplete(req, res)` endpoint handler
  - [ ] Find task and verify ownership
  - [ ] Set status to 'done' and completedAt timestamp
  - [ ] Save and return task
- [ ] 2.11: Add JSDoc comments to all methods
- [ ] 2.12: Add consistent error handling with appropriate status codes

### 3. Task Routes Configuration

- [ ] 3.1: Create `src/routes/tasks.js` with Express router
- [ ] 3.2: Apply `authenticate` middleware to all task routes
- [ ] 3.3: Define `POST /api/tasks` route
  - [ ] Use `validateTask` middleware
  - [ ] Call `TaskController.create`
- [ ] 3.4: Define `GET /api/tasks` route
  - [ ] Call `TaskController.list`
- [ ] 3.5: Define `GET /api/tasks/stats` route
  - [ ] Call `TaskController.getStats`
- [ ] 3.6: Define `GET /api/tasks/search` route
  - [ ] Call `TaskController.search`
- [ ] 3.7: Define `GET /api/tasks/:id` route
  - [ ] Use `ensureTaskOwnership` middleware
  - [ ] Call `TaskController.getById`
- [ ] 3.8: Define `PUT /api/tasks/:id` route
  - [ ] Use `ensureTaskOwnership` middleware
  - [ ] Use `validateTaskUpdate` middleware
  - [ ] Call `TaskController.update`
- [ ] 3.9: Define `DELETE /api/tasks/:id` route
  - [ ] Use `ensureTaskOwnership` middleware
  - [ ] Call `TaskController.delete`
- [ ] 3.10: Define `PATCH /api/tasks/bulk` route
  - [ ] Call `TaskController.bulkUpdate`
- [ ] 3.11: Define `POST /api/tasks/:id/complete` route
  - [ ] Use `ensureTaskOwnership` middleware
  - [ ] Call `TaskController.markComplete`

### 4. Authorization Middleware

- [ ] 4.1: Create `src/middleware/taskAuth.js` with `ensureTaskOwnership()` function
- [ ] 4.2: Extract task ID from request params
- [ ] 4.3: Get authenticated user ID from req.user
- [ ] 4.4: Find task in database
- [ ] 4.5: Verify task exists, return 404 if not
- [ ] 4.6: Verify task.userId matches authenticated user, return 403 if not
- [ ] 4.7: Attach task to req.task for controller use
- [ ] 4.8: Call next() if authorization succeeds
- [ ] 4.9: Write tests for task authorization middleware

### 5. Input Validation Middleware for Tasks

- [ ] 5.1: Create/extend validation for task creation in `src/middleware/validation.js`
- [ ] 5.2: Implement `validateTask()` middleware:
  - [ ] Validate title (required, max 200 chars)
  - [ ] Validate description (optional, max 2000 chars)
  - [ ] Validate status (optional, must be todo/in_progress/done)
  - [ ] Validate priority (optional, must be low/medium/high)
  - [ ] Validate dueDate (optional, must be valid date)
  - [ ] Validate tags (optional, must be array)
  - [ ] Return 400 with error array if validation fails
- [ ] 5.3: Implement `validateTaskUpdate()` middleware:
  - [ ] Similar to validateTask but all fields optional
  - [ ] Require at least one field to be updated
- [ ] 5.4: Add helper functions for common validations
- [ ] 5.5: Write tests for task validation middleware

### 6. Pagination Utilities

- [ ] 6.1: Create `src/utils/pagination.js` utility module
- [ ] 6.2: Implement `paginate(page, limit)` function:
  - [ ] Sanitize page (min 1)
  - [ ] Sanitize limit (min 1, max 100)
  - [ ] Calculate skip value
  - [ ] Return skip and limit
- [ ] 6.3: Implement `paginationMetadata(total, page, limit)` function:
  - [ ] Calculate totalPages
  - [ ] Set hasNext and hasPrev flags
  - [ ] Return metadata object
- [ ] 6.4: Use pagination in TaskRepository.findByUser() method
- [ ] 6.5: Write tests for pagination utilities

### 7. Query Parameter Handling

- [ ] 7.1: Define supported query parameters for list endpoint:
  - [ ] `status` - Filter by status (todo, in_progress, done)
  - [ ] `priority` - Filter by priority (low, medium, high)
  - [ ] `tags` - Filter by tags (comma-separated)
  - [ ] `overdue` - Filter overdue tasks (true/false)
  - [ ] `search` - Search in title and description
  - [ ] `sort` - Sort field (createdAt, dueDate, priority, title)
  - [ ] `order` - Sort order (asc, desc)
  - [ ] `page` - Page number (default 1)
  - [ ] `limit` - Items per page (default 20, max 100)
- [ ] 7.2: Implement query parameter parsing in controller
- [ ] 7.3: Validate and sanitize all query parameters
- [ ] 7.4: Set reasonable defaults (page=1, limit=20, sort=createdAt, order=desc)
- [ ] 7.5: Test query parameter handling with various combinations

### 8. Response Format Standardization

- [ ] 8.1: Create response helper in `src/utils/response.js`
- [ ] 8.2: Define standard success response format:
  ```json
  {
    "success": true,
    "data": {},
    "message": "Optional message"
  }
  ```
- [ ] 8.3: Define list response with pagination:
  ```json
  {
    "success": true,
    "data": [],
    "pagination": {
      "page": 1,
      "limit": 20,
      "total": 45,
      "totalPages": 3,
      "hasNext": true,
      "hasPrev": false
    }
  }
  ```
- [ ] 8.4: Define error response format:
  ```json
  {
    "success": false,
    "error": "Error message",
    "statusCode": 400
  }
  ```
- [ ] 8.5: Use response helpers consistently across all controllers

### 9. Integration Tests for API

- [ ] 9.1: Create `tests/api/tasks.integration.test.js` for API tests
- [ ] 9.2: Test task creation:
  - [ ] Valid task creation returns 201
  - [ ] Created task has correct data
  - [ ] Missing title returns 400
  - [ ] Unauthenticated request returns 401
- [ ] 9.3: Test task listing:
  - [ ] Returns authenticated user's tasks only
  - [ ] Filters work correctly (status, priority, tags)
  - [ ] Pagination works correctly
  - [ ] Sort order is correct
  - [ ] Search finds relevant tasks
- [ ] 9.4: Test task retrieval:
  - [ ] Valid ID returns task
  - [ ] Invalid ID returns 404
  - [ ] Other user's task returns 403
- [ ] 9.5: Test task update:
  - [ ] Valid update modifies task
  - [ ] Invalid data returns 400
  - [ ] Other user's task returns 403
  - [ ] Partial updates work (only update sent fields)
- [ ] 9.6: Test task deletion:
  - [ ] Valid delete removes task
  - [ ] Deleted task cannot be retrieved
  - [ ] Other user's task returns 403
- [ ] 9.7: Test mark complete endpoint
- [ ] 9.8: Test bulk update endpoint
- [ ] 9.9: Test statistics endpoint
- [ ] 9.10: Use supertest for HTTP testing

### 10. Performance Testing

- [ ] 10.1: Create performance tests to verify API response times
- [ ] 10.2: Test endpoint response times: all should be < 100ms
- [ ] 10.3: Test pagination with large datasets (1000+ tasks)
- [ ] 10.4: Test search performance with large datasets
- [ ] 10.5: Test filtering with multiple criteria
- [ ] 10.6: Document any performance bottlenecks found
- [ ] 10.7: Ensure database indexes are utilized

### 11. Error Handling & Edge Cases

- [ ] 11.1: Test empty result sets (no tasks found)
- [ ] 11.2: Test very long task titles (max length validation)
- [ ] 11.3: Test very long descriptions (max length validation)
- [ ] 11.4: Test special characters in search and descriptions
- [ ] 11.5: Test invalid ObjectId format (should return 404, not 500)
- [ ] 11.6: Test concurrent updates to same task
- [ ] 11.7: Test maximum pagination limit exceeded
- [ ] 11.8: All error responses return appropriate status codes

### 12. API Documentation

- [ ] 12.1: Create `docs/api.md` documenting all endpoints:
  - [ ] HTTP method and path
  - [ ] Authentication requirement
  - [ ] Request parameters/body schema
  - [ ] Response schema
  - [ ] Error responses
  - [ ] Example requests and responses
- [ ] 12.2: Create Postman collection for manual testing in `docs/TaskTracker.postman_collection.json`
- [ ] 12.3: Include environment variables in Postman collection
- [ ] 12.4: Document query parameters and examples
- [ ] 12.5: Document authorization and token usage
- [ ] 12.6: Add JSDoc comments to all route handlers

### 13. Integration with Authentication

- [ ] 13.1: Verify all task routes require authentication
- [ ] 13.2: Test that unauthenticated requests return 401
- [ ] 13.3: Test that authenticated user can only access their own tasks
- [ ] 13.4: Verify userId is automatically set from authenticated user
- [ ] 13.5: Test authorization bypass attempts fail

---

## Files to Create/Modify

| File | Action | Purpose |
|------|--------|---------|
| `src/app.js` | Create | Express application setup with middleware |
| `src/server.js` | Create | Server startup and graceful shutdown |
| `src/controllers/TaskController.js` | Create | Task CRUD and related operations |
| `src/routes/tasks.js` | Create | Task API route definitions |
| `src/middleware/taskAuth.js` | Create | Task ownership authorization check |
| `src/middleware/validation.js` | Modify | Add task input validation |
| `src/utils/pagination.js` | Create | Pagination helper functions |
| `src/utils/response.js` | Create | Standard response format helpers |
| `tests/api/tasks.integration.test.js` | Create | Integration tests for API endpoints |
| `tests/middleware/taskAuth.test.js` | Create | Tests for task authorization |
| `docs/api.md` | Create | Complete API documentation |
| `docs/TaskTracker.postman_collection.json` | Create | Postman collection for testing |
| `package.json` | Modify | Add cors, helmet, morgan dependencies |

## Patterns to Follow

| Pattern | Reference | Usage |
|---------|-----------|-------|
| Controller Pattern | `TaskController` | Business logic separated from routing, easier to test |
| Middleware Chain | `authenticate` → `ensureTaskOwnership` → `validateTask` | Validation and auth before controller |
| Repository Pattern | `TaskRepository` from Phase 1 | Data access abstraction, enables testing with mocks |
| Standard Responses | Response helpers | Consistent API response format |
| Pagination | `paginate()` and `paginationMetadata()` | Handle large result sets efficiently |
| Error Handling | Status codes + error responses | Clear error communication to frontend |

## Test Strategy

- [ ] Unit tests for pagination utilities
- [ ] Integration tests for all CRUD endpoints
- [ ] Authorization tests (verify cross-user access prevented)
- [ ] Validation tests (invalid input returns 400)
- [ ] Error handling tests (500 errors, database errors)
- [ ] Performance tests (response times < 100ms)
- [ ] Edge case tests (empty results, max values, special chars)
- [ ] Manual testing with Postman collection

## Acceptance Criteria

**ALL must pass:**

- [ ] All CRUD operations work correctly
- [ ] Filtering and sorting return expected results
- [ ] Search finds relevant tasks
- [ ] Pagination works with large datasets
- [ ] Statistics calculations are accurate
- [ ] Users can only access their own tasks
- [ ] Authentication required for all endpoints
- [ ] Input validation prevents injection attacks
- [ ] Error messages don't leak sensitive info
- [ ] All integration tests pass (>85% coverage)
- [ ] API endpoints respond in <100ms
- [ ] ESLint passes with 0 errors
- [ ] npm audit shows no high severity vulnerabilities
- [ ] API documentation is complete and accurate
- [ ] Postman collection is functional

## Rollback Plan

If Phase 3 encounters critical issues:

1. **Failed API tests:** Review test errors, debug controller logic, rerun tests
2. **Authorization vulnerabilities:** 
   - Verify `ensureTaskOwnership` middleware is on all protected routes
   - Check that req.user is properly attached by auth middleware
   - Review authorization logic for logic errors
3. **Performance issues:**
   - Verify database indexes exist on userId, status, createdAt
   - Check query patterns in TaskRepository
   - Use MongoDB explain() to verify index usage
4. **Validation bypass:**
   - Verify validation middleware is on all write endpoints
   - Check validation logic for edge cases
   - Add additional tests for edge cases
5. **Complete rollback:**
   - Delete Node modules and reinstall: `rm -rf node_modules && npm install`
   - Revert code changes: `git reset --hard HEAD`
   - Restart database with clean state
   - Restart development

---

## Implementation Notes

This phase implements the complete REST API for task management. Key architectural decisions:

1. **Controller/Repository Separation:** Controllers handle HTTP concerns and validation, repositories handle data access. Makes testing easier and follows separation of concerns.

2. **Standard Response Format:** All endpoints return consistent response format, simplifying frontend error handling and data extraction.

3. **Pagination From the Start:** Built into list endpoint to handle large datasets efficiently and prevent performance issues.

4. **Authorization on Every Operation:** ensureTaskOwnership middleware on all protected routes prevents accidental cross-user data access.

5. **Comprehensive Query Parameters:** Support filtering by multiple criteria (status, priority, tags, search) without requiring multiple API changes.