# TaskTracker MVP Phase 3: Task API Implementation

**Status:** Pending
**Master Plan:** [tasktracker-mvp-MASTER_PLAN.md](tasktracker-mvp-MASTER_PLAN.md)
**Depends On:** [Phase 1: Data Layer Foundation](tasktracker-mvp-phase-1.md), [Phase 2: Authentication System](tasktracker-mvp-phase-2.md)

---

## Process Wrapper (MANDATORY)
- [ ] Read previous notes: `notes/NOTES_tasktracker_phase_1.md`, `notes/NOTES_tasktracker_phase_2.md`
- [ ] **[IMPLEMENTATION - see Tasks below]**
- [ ] Pre-validation (ALL required):
  ```bash
  # Code quality
  npm run lint --fix
  npm run test
  npm audit
  ```
- [ ] Fix loop: repeat pre-validation until clean
- [ ] Write `notes/NOTES_tasktracker_phase_3.md` (REQUIRED)

## Gates (must pass before completion)

**ALL gates are BLOCKING.**

- lint: `npm run lint` - 0 errors
- tests: `npm test` - All tests pass (>85% coverage for API code)
- security: `npm audit` - No high or critical severity issues
- performance: API endpoints respond within 100ms for typical queries

---

## Overview

Build the REST API for task management operations. This phase provides endpoints for creating, reading, updating, and deleting tasks, with filtering, search, pagination, and statistics. All endpoints will be protected with authentication middleware and enforce proper authorization (users can only access their own tasks).

## Dependencies
- Previous phase: [Phase 1: Data Layer Foundation](tasktracker-mvp-phase-1.md) - requires Task model and TaskRepository
- Previous phase: [Phase 2: Authentication System](tasktracker-mvp-phase-2.md) - requires auth middleware
- External: express, cors, helmet, morgan

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Authorization bypass (users accessing others' tasks) | Low | High | Comprehensive ownership checks, extensive integration tests |
| Performance issues with large datasets | Low | Medium | Implement pagination, indexes (done in Phase 1), performance testing |
| Input validation gaps | Medium | Medium | Strict validation middleware, test edge cases, sanitize inputs |
| API design inconsistencies | Low | Low | Follow REST conventions, document API clearly, peer review |
| SQL/NoSQL injection | Low | High | Use Mongoose (parameterized queries), validate all inputs |

---

## Tasks

### 1. Express Application Setup
- [ ] 1.1: Install dependencies: `express`, `cors`, `helmet`, `morgan`
- [ ] 1.2: Create `src/app.js` with Express application configuration
- [ ] 1.3: Configure security middleware (helmet)
- [ ] 1.4: Configure CORS for frontend origin
- [ ] 1.5: Configure request logging (morgan)
- [ ] 1.6: Configure body parsing (JSON and URL-encoded)
- [ ] 1.7: Add health check endpoint GET /health
- [ ] 1.8: Add 404 handler for unknown routes
- [ ] 1.9: Add global error handler middleware

### 2. Task Controller
- [ ] 2.1: Create `src/controllers/TaskController.js`
- [ ] 2.2: Implement `create(req, res)` - POST /api/tasks
- [ ] 2.3: Implement `list(req, res)` - GET /api/tasks with filtering/pagination
- [ ] 2.4: Implement `getById(req, res)` - GET /api/tasks/:id
- [ ] 2.5: Implement `update(req, res)` - PUT /api/tasks/:id
- [ ] 2.6: Implement `delete(req, res)` - DELETE /api/tasks/:id
- [ ] 2.7: Implement `search(req, res)` - GET /api/tasks/search
- [ ] 2.8: Implement `getStats(req, res)` - GET /api/tasks/stats
- [ ] 2.9: Implement `bulkUpdate(req, res)` - PATCH /api/tasks/bulk
- [ ] 2.10: Implement `markComplete(req, res)` - POST /api/tasks/:id/complete

### 3. Task Routes
- [ ] 3.1: Create `src/routes/tasks.js`
- [ ] 3.2: Apply authenticate middleware to all routes
- [ ] 3.3: Define POST / route with validateTask middleware
- [ ] 3.4: Define GET / route for list
- [ ] 3.5: Define GET /stats route
- [ ] 3.6: Define GET /search route
- [ ] 3.7: Define GET /:id route
- [ ] 3.8: Define PUT /:id route with validateTaskUpdate middleware
- [ ] 3.9: Define DELETE /:id route
- [ ] 3.10: Define PATCH /bulk route
- [ ] 3.11: Define POST /:id/complete route
- [ ] 3.12: Mount task routes in `src/app.js`

### 4. Query Parameter Handling
- [ ] 4.1: Implement filtering by status (todo, in_progress, done)
- [ ] 4.2: Implement filtering by priority (low, medium, high)
- [ ] 4.3: Implement filtering by tags (comma-separated)
- [ ] 4.4: Implement filtering by overdue (true/false)
- [ ] 4.5: Implement search in title and description
- [ ] 4.6: Implement sorting (createdAt, dueDate, priority, title)
- [ ] 4.7: Implement sort order (asc, desc)
- [ ] 4.8: Test example queries with multiple filters

### 5. Pagination
- [ ] 5.1: Create `src/utils/pagination.js`
- [ ] 5.2: Implement `paginate(page, limit)` helper function
- [ ] 5.3: Implement `paginationMetadata(total, page, limit)` helper
- [ ] 5.4: Set default page=1, limit=20, max limit=100
- [ ] 5.5: Apply pagination to list endpoint
- [ ] 5.6: Return pagination metadata in list response
- [ ] 5.7: Test pagination with large datasets

### 6. Task Validation Middleware
- [ ] 6.1: Extend `src/middleware/validation.js`
- [ ] 6.2: Implement `validateTask(req, res, next)` for create
- [ ] 6.3: Validate title (required, max 200 chars)
- [ ] 6.4: Validate description (optional, max 2000 chars)
- [ ] 6.5: Validate status enum (todo, in_progress, done)
- [ ] 6.6: Validate priority enum (low, medium, high)
- [ ] 6.7: Validate dueDate format
- [ ] 6.8: Validate tags array format
- [ ] 6.9: Implement `validateTaskUpdate(req, res, next)` for updates
- [ ] 6.10: Write validation tests

### 7. Authorization Middleware
- [ ] 7.1: Create `src/middleware/taskAuth.js`
- [ ] 7.2: Implement `ensureTaskOwnership(req, res, next)` middleware
- [ ] 7.3: Verify task exists (404 if not found)
- [ ] 7.4: Verify task belongs to authenticated user (403 if not)
- [ ] 7.5: Attach task to req.task for controller use
- [ ] 7.6: Apply to GET/:id, PUT/:id, DELETE/:id routes
- [ ] 7.7: Write authorization tests

### 8. Response Formatting
- [ ] 8.1: Define standard success response format {success, data, message}
- [ ] 8.2: Define list response format with pagination metadata
- [ ] 8.3: Define error response format {success, error, statusCode}
- [ ] 8.4: Implement consistent response helpers
- [ ] 8.5: Test response formats across all endpoints

### 9. Integration Testing
- [ ] 9.1: Test task creation: valid task, missing title, unauthenticated request
- [ ] 9.2: Test task listing: returns user's tasks only, filters work, pagination works, sort order correct
- [ ] 9.3: Test task retrieval: valid ID, invalid ID (404), other user's task (403)
- [ ] 9.4: Test task update: valid update, invalid data, other user's task, partial update
- [ ] 9.5: Test task deletion: valid delete, deleted task cannot be retrieved, other user's task (403)
- [ ] 9.6: Test search: finds by title, finds by description, case-insensitive, empty results
- [ ] 9.7: Test statistics: correct counts by status, correct counts by priority, overdue count
- [ ] 9.8: Test bulk update: multiple tasks, ownership verification
- [ ] 9.9: Test mark complete: sets status and timestamp correctly

### 10. Edge Cases & Performance
- [ ] 10.1: Test empty result sets
- [ ] 10.2: Test very long task titles/descriptions
- [ ] 10.3: Test special characters in search
- [ ] 10.4: Test invalid ObjectId format
- [ ] 10.5: Test concurrent updates to same task
- [ ] 10.6: Benchmark API response times (<100ms target)
- [ ] 10.7: Test with large datasets (1000+ tasks per user)

### 11. API Documentation
- [ ] 11.1: Create `docs/api.md`
- [ ] 11.2: Document all endpoints with HTTP method, path, auth requirements
- [ ] 11.3: Document request parameters and body schemas
- [ ] 11.4: Document response schemas and error responses
- [ ] 11.5: Provide example requests and responses for each endpoint
- [ ] 11.6: Create Postman collection for manual testing
- [ ] 11.7: Consider adding Swagger/OpenAPI spec (optional)

---

## Files to Create/Modify

| File | Action | Purpose |
|------|--------|---------|
| `src/app.js` | Create | Express application configuration |
| `src/controllers/TaskController.js` | Create | Task CRUD operations logic |
| `src/routes/tasks.js` | Create | Task route definitions |
| `src/middleware/taskAuth.js` | Create | Task ownership authorization |
| `src/middleware/validation.js` | Modify | Add task validation middleware |
| `src/utils/pagination.js` | Create | Pagination helper functions |
| `tests/api/TaskController.test.js` | Create | Task controller integration tests |
| `tests/api/routes.test.js` | Create | Route integration tests |
| `tests/middleware/taskAuth.test.js` | Create | Authorization middleware tests |
| `docs/api.md` | Create | API documentation |
| `postman/tasktracker.json` | Create | Postman collection for manual testing |
| `.env.example` | Modify | Add FRONTEND_URL, PORT |
| `README.md` | Modify | Add API usage documentation |

## Patterns to Follow

| Pattern | Reference | Usage |
|---------|-----------|-------|
| RESTful API Design | REST principles | Use proper HTTP methods, status codes, resource naming |
| Controller-Service Pattern | `src/controllers/`, `src/repositories/` | Controllers handle HTTP, services handle business logic |
| Middleware Composition | Express middleware | Chain validation -> auth -> authorization -> controller |
| Pagination Pattern | `src/utils/pagination.js` | Consistent pagination across all list endpoints |
| Error Response Format | Standard JSON | Consistent error structure for client handling |

## Test Strategy

- [ ] Integration tests for all CRUD endpoints: success cases, error cases, authentication, authorization
- [ ] Test filtering and sorting return expected results
- [ ] Test pagination works with large datasets
- [ ] Test search finds relevant tasks (case-insensitive, title + description)
- [ ] Test statistics calculations are accurate
- [ ] Test authorization prevents cross-user access
- [ ] Test edge cases: empty results, invalid IDs, special characters, concurrent updates
- [ ] Performance testing: response times <100ms for typical queries
- [ ] Use isolated test database, clean up after each test

## Validation

- Use `python-task-validator` to verify code quality, API design patterns, and security practices

## Acceptance Criteria

**ALL must pass:**

- [ ] All tasks completed
- [ ] All gates passing (lint, tests, security, performance)
- [ ] Integration tests achieve >85% coverage
- [ ] All CRUD operations work correctly
- [ ] Users can only access their own tasks (authorization enforced)
- [ ] Filtering and sorting return expected results
- [ ] Search finds relevant tasks
- [ ] Pagination works with large datasets
- [ ] Statistics calculations are accurate
- [ ] Input validation prevents invalid data
- [ ] Error messages are helpful and don't leak sensitive info
- [ ] API response times <100ms for typical queries
- [ ] API documentation complete with examples
- [ ] Postman collection works for manual testing

## Rollback Plan

If API has critical issues:
1. Revert commits related to Phase 3
2. Remove task routes from Express app
3. Keep data layer (Phase 1) and auth (Phase 2) intact
4. Drop test data from Task collection if needed: `db.tasks.deleteMany({})`

For production (if already deployed):
1. Take API offline or add maintenance mode middleware
2. Backup Task collection before any data fixes
3. Identify affected endpoints and disable them specifically
4. Apply fix and redeploy
5. Verify fix with integration tests
6. Re-enable endpoints and monitor logs
7. Notify users if data integrity was affected

---

## Implementation Notes

### Query Parameter Examples
```
GET /api/tasks?status=todo&priority=high
GET /api/tasks?overdue=true&sort=dueDate&order=asc
GET /api/tasks?tags=work,urgent&page=2&limit=10
GET /api/tasks?search=meeting&sort=createdAt&order=desc
```

### Response Format Examples

**Success Response:**
```json
{
  "success": true,
  "data": {
    "_id": "507f1f77bcf86cd799439011",
    "title": "Complete project proposal",
    "status": "todo",
    "priority": "high"
  },
  "message": "Task created successfully"
}
```

**List Response:**
```json
{
  "success": true,
  "data": [ /* array of tasks */ ],
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

**Error Response:**
```json
{
  "success": false,
  "error": "Task not found",
  "statusCode": 404
}
```

### HTTP Status Codes
- 200 OK - Successful GET, PUT requests
- 201 Created - Successful POST (create)
- 204 No Content - Successful DELETE
- 400 Bad Request - Invalid input
- 401 Unauthorized - Missing/invalid token
- 403 Forbidden - Valid token but insufficient permissions
- 404 Not Found - Resource doesn't exist
- 409 Conflict - Duplicate resource
- 500 Internal Server Error - Unexpected errors

### Performance Optimization
- Indexes already created in Phase 1 (userId, status, createdAt, compound)
- Pagination limits result sets (max 100 per page)
- Use projection to return only needed fields
- Monitor slow query logs in MongoDB
- Consider caching for stats endpoint (future enhancement)