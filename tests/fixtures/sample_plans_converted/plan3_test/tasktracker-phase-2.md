# TaskTracker MVP Phase 2: Authentication Module

**Status:** Pending
**Master Plan:** [TaskTracker MVP - Master Plan](MASTER_PLAN.md)
**Depends On:** [Phase 1: Data Layer](tasktracker-phase-1.md)

---

## Process Wrapper (MANDATORY)
- [ ] Read previous notes: `notes/NOTES_phase_1_data.md`
- [ ] Verify Phase 1 is complete and all gates passing
- [ ] **[IMPLEMENTATION - see Tasks below]**
- [ ] Pre-validation (ALL required):
  ```bash
  npm run lint --fix
  npm run type-check
  npm test
  ```
- [ ] Fix loop: repeat pre-validation until clean
- [ ] Write `notes/NOTES_phase_2_auth.md` (REQUIRED)

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

---

## Overview

Implement user registration, login, and JWT-based authentication. This phase builds on the User model from Phase 1 and provides the security foundation for the application. Password hashing, token generation, and authentication middleware are critical to the application's security posture.

## Dependencies
- Previous phase: [Phase 1: Data Layer](tasktracker-phase-1.md) - requires User model and UserRepository
- External: bcryptjs, jsonwebtoken, supertest (for testing)

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| JWT secret hardcoded or exposed | Low | Critical | Use environment variables, never commit secrets, document in security guide |
| Weak password requirements | Low | High | Implement complexity rules (uppercase, lowercase, number, length), test extensively |
| Token expiration not enforced | Low | High | Set short expiration (7d), implement token refresh strategy, test expiration |
| Sensitive data in error messages | Medium | Medium | Use generic error messages for login failures, log detailed errors server-side only |
| Race condition in user creation | Low | Medium | Rely on MongoDB unique index + catch duplicate key error, test concurrent registrations |

---

## Tasks

### 1. Security Configuration and Password Handling
- [ ] 1.1: Create auth configuration in `src/config/auth.js` with JWT and bcrypt settings
- [ ] 1.2: Create PasswordService in `src/services/PasswordService.js` for hashing and comparison
- [ ] 1.3: Implement password validation with complexity requirements (uppercase, lowercase, number, min 8 chars)
- [ ] 1.4: Implement password comparison using bcryptjs
- [ ] 1.5: Write unit tests for PasswordService (hashing, comparison, validation)

### 2. JWT Token Management
- [ ] 2.1: Create TokenService in `src/services/TokenService.js` for JWT operations
- [ ] 2.2: Implement token generation with payload (userId, email, iat, exp)
- [ ] 2.3: Implement token verification with expiration checking
- [ ] 2.4: Implement token decoding for debugging
- [ ] 2.5: Write unit tests for TokenService (generation, verification, expiration, errors)

### 3. Authentication Controller
- [ ] 3.1: Create AuthController in `src/controllers/AuthController.js`
- [ ] 3.2: Implement register endpoint (validation, user creation, token generation)
- [ ] 3.3: Implement login endpoint (find user, password comparison, token generation)
- [ ] 3.4: Implement getCurrentUser endpoint (return authenticated user)
- [ ] 3.5: Implement changePassword endpoint (verify current password, update, generate new token)
- [ ] 3.6: Write integration tests for all AuthController methods

### 4. Authentication Middleware and Routes
- [ ] 4.1: Create authentication middleware in `src/middleware/auth.js` (authenticate, optionalAuth)
- [ ] 4.2: Implement token extraction from Authorization header
- [ ] 4.3: Create auth routes in `src/routes/auth.js` (register, login, me, change-password)
- [ ] 4.4: Create input validation middleware in `src/middleware/validation.js` (validateRegistration, validateLogin)
- [ ] 4.5: Write integration tests for middleware (valid token, invalid token, missing token, expired token)

### 5. Error Handling and Security
- [ ] 5.1: Create AuthError class extending Error with statusCode
- [ ] 5.2: Create centralized error handler in `src/middleware/errorHandler.js`
- [ ] 5.3: Implement error logging without exposing sensitive information
- [ ] 5.4: Test error handling for all failure scenarios
- [ ] 5.5: Implement rate limiting considerations (document but don't implement yet)

### 6. Testing and Documentation
- [ ] 6.1: Write unit tests for PasswordService in `tests/auth/PasswordService.test.js`
- [ ] 6.2: Write unit tests for TokenService in `tests/auth/TokenService.test.js`
- [ ] 6.3: Write integration tests for endpoints in `tests/auth/endpoints.test.js` using supertest
- [ ] 6.4: Write security tests (password never logged, token validation, bcrypt settings)
- [ ] 6.5: Write test for duplicate email/username registration
- [ ] 6.6: Achieve >85% test coverage for Phase 2
- [ ] 6.7: Create API documentation for auth endpoints
- [ ] 6.8: Document password requirements and JWT token format

---

## Files to Create/Modify

| File | Action | Purpose |
|------|--------|---------|
| `src/config/auth.js` | Create | JWT secret, expiration, bcrypt settings |
| `src/services/PasswordService.js` | Create | Password hashing, comparison, validation |
| `src/services/TokenService.js` | Create | JWT generation, verification, decoding |
| `src/controllers/AuthController.js` | Create | Register, login, getCurrentUser, changePassword handlers |
| `src/middleware/auth.js` | Create | Token verification and user attachment middleware |
| `src/middleware/validation.js` | Modify | Add registration and login validation |
| `src/middleware/errorHandler.js` | Create | Centralized error handling for auth and other errors |
| `src/routes/auth.js` | Create | POST/register, POST/login, GET/me, POST/change-password |
| `tests/auth/PasswordService.test.js` | Create | Unit tests for password operations |
| `tests/auth/TokenService.test.js` | Create | Unit tests for token operations |
| `tests/auth/endpoints.test.js` | Create | Integration tests for auth endpoints |
| `.env` | Modify | Add JWT_SECRET, JWT_EXPIRES_IN, BCRYPT_SALT_ROUNDS |

## Patterns to Follow

| Pattern | Reference | Usage |
|---------|-----------|-------|
| Service Layer | PasswordService, TokenService | Encapsulate auth logic, make testable and reusable |
| Error Classes | AuthError extending Error | Provide statusCode for error responses |
| Middleware Chain | auth.js + validation.js | Compose middleware for route protection and validation |
| Repository Injection | Repositories from Phase 1 | Keep services independent of database layer |
| Test Isolation | Separate test database | Each test creates/clears test users independently |

## Test Strategy

- [ ] Unit tests for PasswordService (hashing produces different output, comparison works, validation catches weak passwords)
- [ ] Unit tests for TokenService (generation, verification, expiration, invalid tokens)
- [ ] Integration tests for registration (valid, duplicate email, invalid input, weak password)
- [ ] Integration tests for login (valid credentials, invalid email, invalid password, user not found)
- [ ] Integration tests for getCurrentUser (valid token, invalid token, missing token)
- [ ] Integration tests for changePassword (correct current password, incorrect current password, weak new password)
- [ ] Security tests (passwords never returned in responses, JWT secret not hardcoded, tokens expire correctly)
- [ ] Concurrent registration tests (prevent duplicate users with simultaneous requests)

## Acceptance Criteria

**ALL must pass:**

- [ ] All tasks completed as specified
- [ ] All gates passing (lint, type-check, tests, security audit)
- [ ] Test coverage exceeds 85% for Phase 2
- [ ] Users can register with valid email, username, and password
- [ ] Users can log in with correct credentials
- [ ] JWT tokens are generated and can be used to access protected routes
- [ ] Protected routes reject requests without valid tokens
- [ ] Password complexity requirements are enforced
- [ ] No sensitive data (passwords, token secrets) in responses or logs
- [ ] Error messages are helpful but don't leak information
- [ ] Password change works correctly and updates user record

## Rollback Plan

If Phase 2 fails validation:
1. Reset to Phase 1 completion: `git reset --hard <phase_1_complete_commit>`
2. Review failed authentication tests in test output
3. Check security audit results for dependency issues: `npm audit`
4. Reset test database: `npm run db:reset`
5. If password hashing tests failed, verify bcryptjs is installed correctly
6. If token tests failed, verify JWT_SECRET is properly set in test environment
7. Fix identified issues and re-run all gates
8. If integration tests still fail, manually test auth flow with Postman before continuing

---

## Implementation Notes

{To be filled during implementation}