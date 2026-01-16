# TaskTracker MVP Phase 2: Authentication System

**Status:** Pending
**Master Plan:** [TaskTracker MVP - Master Plan](MASTER_PLAN.md)
**Depends On:** [Phase 1: Data Layer Foundation](phase-1.md)

---

## Process Wrapper (MANDATORY)

- [ ] Review previous notes: `notes/NOTES_phase1_data_layer.md`
- [ ] Install authentication dependencies: `npm install bcryptjs jsonwebtoken && npm install --save-dev supertest`
- [ ] **[IMPLEMENTATION - see Tasks below]**
- [ ] Pre-validation (ALL required):
  ```bash
  # Code quality and testing
  npm run lint --fix
  npm test -- --coverage
  npm audit
  ```
- [ ] Fix loop: repeat pre-validation until clean
- [ ] Write `notes/NOTES_phase2_authentication.md` (REQUIRED)

## Gates (must pass before completion)

**ALL gates are BLOCKING.**

- lint: 0 errors
- tests: All authentication tests pass
- coverage: >85% coverage on auth services and controllers
- security: npm audit shows no high severity vulnerabilities, bcrypt salt rounds >= 10

---

## Overview

Implement user registration, login, and JWT-based authentication system. This phase provides the security foundation for the application, including password hashing with bcrypt, JWT token generation and verification, authentication middleware, input validation, and comprehensive security tests.

## Dependencies
- Previous phase: Phase 1 (Data Layer Foundation with User model and UserRepository)
- External: bcryptjs, jsonwebtoken libraries

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| JWT secret leaked in logs | Low | High | Never log tokens, sanitize logs, use environment variables only |
| Weak password hashing | Low | High | Use bcrypt with salt rounds >= 10, never implement custom hashing |
| Token expiration not enforced | Medium | High | Set short expiry times (7d), verify expiration in middleware, implement token refresh |
| Common password allowed | Medium | Medium | Validate against list of common passwords, enforce complexity requirements |
| Concurrent login attacks | Low | Medium | Implement rate limiting on login endpoint (Phase 3), log suspicious activity |
| Password reset vulnerable | N/A | High | Out of scope for MVP, document for v2 |

---

## Tasks

### 1. Security Configuration

- [ ] 1.1: Create `src/config/auth.js` with JWT secret, expiration, algorithm, and bcrypt settings
- [ ] 1.2: Define password complexity requirements (minLength: 8, uppercase, lowercase, number)
- [ ] 1.3: Create list of common passwords to block in `src/config/commonPasswords.js`
- [ ] 1.4: Configure JWT to use HS256 algorithm and 7d expiration
- [ ] 1.5: Set bcrypt salt rounds to 10 (NIST recommendation)
- [ ] 1.6: Ensure JWT_SECRET is loaded from environment, never hardcoded

### 2. Password Service Implementation

- [ ] 2.1: Create `src/services/PasswordService.js` class
- [ ] 2.2: Implement `hash(password)` method using bcryptjs with configured salt rounds
- [ ] 2.3: Implement `compare(password, hash)` method to verify passwords
- [ ] 2.4: Implement `validate(password)` method to check complexity requirements
- [ ] 2.5: Add common password validation to `validate()` method
- [ ] 2.6: Return helpful error messages for failed validation
- [ ] 2.7: Add JSDoc comments documenting all methods
- [ ] 2.8: Write unit tests for PasswordService in `tests/services/PasswordService.test.js`
- [ ] 2.9: Test hashing produces different output (salt), compare logic, validation rules, common password blocking

### 3. Token Service Implementation

- [ ] 3.1: Create `src/services/TokenService.js` class
- [ ] 3.2: Implement `generate(user)` method to create JWT tokens with userId and email
- [ ] 3.3: Implement `verify(token)` method to verify token signature and expiration
- [ ] 3.4: Implement `decode(token)` method for debugging without verification
- [ ] 3.5: Add error handling with meaningful messages (expired, invalid signature, etc.)
- [ ] 3.6: Add JSDoc comments documenting all methods
- [ ] 3.7: Write unit tests for TokenService in `tests/services/TokenService.test.js`
- [ ] 3.8: Test token generation, verification, expiration, invalid tokens, payload contents

### 4. Authentication Controller

- [ ] 4.1: Create `src/controllers/AuthController.js` class
- [ ] 4.2: Implement `register(req, res)` endpoint handler
  - [ ] Validate input (email, username, password)
  - [ ] Check if user already exists
  - [ ] Validate password complexity
  - [ ] Hash password using PasswordService
  - [ ] Create user in database
  - [ ] Generate JWT token
  - [ ] Return user data and token
- [ ] 4.3: Implement `login(req, res)` endpoint handler
  - [ ] Validate input (email, password)
  - [ ] Find user by email
  - [ ] Compare password with hash
  - [ ] Generate JWT token
  - [ ] Return user data and token
- [ ] 4.4: Implement `getCurrentUser(req, res)` endpoint handler
  - [ ] Return authenticated user data (no password)
- [ ] 4.5: Implement `changePassword(req, res)` endpoint handler
  - [ ] Verify current password
  - [ ] Validate new password
  - [ ] Hash new password
  - [ ] Update user record
- [ ] 4.6: Add consistent error responses with appropriate status codes
- [ ] 4.7: Write integration tests for AuthController in `tests/controllers/AuthController.test.js`

### 5. Authentication Middleware

- [ ] 5.1: Create `src/middleware/auth.js` with `authenticate()` function
- [ ] 5.2: Extract JWT token from Authorization header
- [ ] 5.3: Verify token validity using TokenService
- [ ] 5.4: Decode token to get user ID
- [ ] 5.5: Load user from database
- [ ] 5.6: Attach user object to `req.user`
- [ ] 5.7: Return 401 Unauthorized for invalid/missing tokens
- [ ] 5.8: Implement `optionalAuth()` for routes that don't require authentication
- [ ] 5.9: Write tests for middleware in `tests/middleware/auth.test.js`
- [ ] 5.10: Test valid token, missing token, expired token, invalid token cases

### 6. Input Validation Middleware

- [ ] 6.1: Create or extend `src/middleware/validation.js`
- [ ] 6.2: Implement `validateRegistration()` middleware
  - [ ] Validate email format
  - [ ] Validate username (3-30 chars, alphanumeric+underscore)
  - [ ] Validate password using PasswordService.validate()
  - [ ] Return 400 with error array if validation fails
- [ ] 6.3: Implement `validateLogin()` middleware
  - [ ] Validate email and password presence
- [ ] 6.4: Add reusable validation helper functions
- [ ] 6.5: Write tests for validation middleware

### 7. Routes Configuration

- [ ] 7.1: Create `src/routes/auth.js` with Express router
- [ ] 7.2: Define `POST /api/auth/register` route
  - [ ] Use `validateRegistration` middleware
  - [ ] Call `AuthController.register`
- [ ] 7.3: Define `POST /api/auth/login` route
  - [ ] Use `validateLogin` middleware
  - [ ] Call `AuthController.login`
- [ ] 7.4: Define `GET /api/auth/me` route
  - [ ] Use `authenticate` middleware
  - [ ] Call `AuthController.getCurrentUser`
- [ ] 7.5: Define `POST /api/auth/change-password` route
  - [ ] Use `authenticate` middleware
  - [ ] Call `AuthController.changePassword`
- [ ] 7.6: Add 404 handler for unmatched auth routes

### 8. Error Handling

- [ ] 8.1: Create or extend `src/middleware/errorHandler.js`
- [ ] 8.2: Implement `AuthError` class extending Error
- [ ] 8.3: Define error types: 400 (bad request), 401 (unauthorized), 409 (conflict), 500 (server error)
- [ ] 8.4: Add global error handler middleware
- [ ] 8.5: Never log sensitive information (passwords, tokens)
- [ ] 8.6: Return user-friendly error messages
- [ ] 8.7: Include stack trace only in development mode
- [ ] 8.8: Write tests for error handling

### 9. Integration & End-to-End Testing

- [ ] 9.1: Create `tests/auth/auth.integration.test.js` for end-to-end flows
- [ ] 9.2: Test registration endpoint:
  - [ ] Valid registration creates user and returns token
  - [ ] Duplicate email returns 409 conflict
  - [ ] Invalid email returns 400
  - [ ] Weak password returns 400
  - [ ] Password is hashed (not plain text)
- [ ] 9.3: Test login endpoint:
  - [ ] Valid credentials return token
  - [ ] Invalid email returns 401
  - [ ] Invalid password returns 401
  - [ ] Token can be used to access protected routes
- [ ] 9.4: Test authentication middleware:
  - [ ] Valid token allows access
  - [ ] Missing token returns 401
  - [ ] Invalid token returns 401
  - [ ] Expired token returns 401
- [ ] 9.5: Test change password:
  - [ ] Correct current password allows change
  - [ ] Incorrect current password returns 401
  - [ ] Weak new password returns 400
  - [ ] Password updated in database

### 10. Security Testing

- [ ] 10.1: Create `tests/auth/security.test.js` for security validation
- [ ] 10.2: Verify passwords are never logged
- [ ] 10.3: Verify password hashes are never returned in responses
- [ ] 10.4: Verify JWT secret is not hardcoded
- [ ] 10.5: Verify tokens expire as configured
- [ ] 10.6: Verify bcrypt salt rounds are >= 10
- [ ] 10.7: Verify no SQL injection vectors in validation
- [ ] 10.8: Run npm audit and document any findings

### 11. Environment Configuration

- [ ] 11.1: Add to `.env.example`:
  - [ ] `JWT_SECRET` (example value)
  - [ ] `JWT_EXPIRES_IN` (7d)
  - [ ] `BCRYPT_SALT_ROUNDS` (10)
  - [ ] `NODE_ENV` (development/production)
- [ ] 11.2: Document that JWT_SECRET must be changed in production
- [ ] 11.3: Document how to generate JWT_SECRET: `openssl rand -base64 32`
- [ ] 11.4: Never commit `.env` file to version control

### 12. Documentation

- [ ] 12.1: Create `docs/AUTHENTICATION.md` documenting:
  - [ ] Password requirements and validation rules
  - [ ] JWT token format and lifetime
  - [ ] Authentication flow diagrams
  - [ ] Example API requests (register, login, protected endpoint)
- [ ] 12.2: Add JSDoc comments to all exported functions
- [ ] 12.3: Document security decisions and trade-offs
- [ ] 12.4: Create API documentation for auth endpoints (for Phase 3)

---

## Files to Create/Modify

| File | Action | Purpose |
|------|--------|---------|
| `src/config/auth.js` | Create | JWT and bcrypt configuration |
| `src/config/commonPasswords.js` | Create | List of weak passwords to reject |
| `src/services/PasswordService.js` | Create | Password hashing and validation service |
| `src/services/TokenService.js` | Create | JWT token generation and verification |
| `src/controllers/AuthController.js` | Create | Registration and login logic |
| `src/middleware/auth.js` | Create | JWT authentication middleware |
| `src/middleware/validation.js` | Create/Modify | Input validation for auth endpoints |
| `src/middleware/errorHandler.js` | Create/Modify | Centralized error handling |
| `src/routes/auth.js` | Create | Authentication route definitions |
| `tests/services/PasswordService.test.js` | Create | Unit tests for password service |
| `tests/services/TokenService.test.js` | Create | Unit tests for token service |
| `tests/controllers/AuthController.test.js` | Create | Integration tests for auth controller |
| `tests/middleware/auth.test.js` | Create | Tests for authentication middleware |
| `tests/auth/auth.integration.test.js` | Create | End-to-end authentication tests |
| `tests/auth/security.test.js` | Create | Security vulnerability tests |
| `docs/AUTHENTICATION.md` | Create | Authentication system documentation |
| `.env.example` | Modify | Add auth environment variables |
| `package.json` | Modify | Add bcryptjs and jsonwebtoken dependencies |

## Patterns to Follow

| Pattern | Reference | Usage |
|---------|-----------|-------|
| Service Layer | `PasswordService`, `TokenService` | Encapsulate business logic, enable testing with mocks |
| Middleware Chain | `validateRegistration` → `AuthController.register` | Validate early, keep controllers clean |
| Error Handling | `AuthError` class | Consistent error responses across endpoints |
| JWT in Headers | `Authorization: Bearer <token>` | Standard practice, allows stateless authentication |
| Hash Verification | bcrypt.compare() | Never compare plain text, always hash before comparing |

## Test Strategy

- [ ] Unit tests for PasswordService (hashing, comparison, validation)
- [ ] Unit tests for TokenService (generation, verification, decoding)
- [ ] Unit tests for validation middleware (email, username, password rules)
- [ ] Integration tests for all auth endpoints (register, login, me, change-password)
- [ ] Security tests (password hashing, token security, input validation)
- [ ] Error handling tests (invalid input, duplicate user, wrong password)
- [ ] Edge case tests (very long passwords, special characters in email/username)

## Acceptance Criteria

**ALL must pass:**

- [ ] All unit tests pass (>90% coverage for services)
- [ ] All integration tests pass (>85% coverage for controllers)
- [ ] All security tests pass
- [ ] ESLint passes with 0 errors
- [ ] npm audit shows no high severity vulnerabilities
- [ ] Password hashing uses bcrypt with proper salt rounds
- [ ] JWT tokens expire and are validated correctly
- [ ] All documentation is complete and accurate
- [ ] Error responses are consistent and helpful
- [ ] No sensitive data in logs or error messages

## Rollback Plan

If Phase 2 encounters critical issues:

1. **Failed authentication tests:** Review test failures, debug implementation, rerun tests
2. **Token validation issues:** 
   - Verify JWT_SECRET is set and matches in all environments
   - Check token expiration time is configured
   - Verify TokenService.verify() is called before using token payload
3. **Password hashing issues:**
   - Verify bcrypt salt rounds >= 10
   - Ensure hashed passwords are never logged
   - Rerun PasswordService tests
4. **Security vulnerabilities found:**
   - Review npm audit output
   - Update vulnerable dependencies to patch versions
   - Rerun security tests
5. **Complete rollback:**
   - Delete Node modules and reinstall: `rm -rf node_modules && npm install`
   - Revert code changes: `git reset --hard HEAD`
   - Restart development with clean state

---

## Implementation Notes

This phase implements the security foundation for the application. Key architectural decisions:

1. **Service Layer for Security:** PasswordService and TokenService encapsulate sensitive operations and make testing easier with mocks.

2. **Middleware Chain:** Validation middleware runs before controllers, keeping business logic clean and enabling reuse.

3. **Stateless JWT:** JWT tokens allow scaling without session storage. Short expiration (7d) limits damage from compromised tokens.

4. **Bcrypt Best Practices:** Salt rounds set to 10 (NIST recommendation) provides good security/performance balance.

5. **Common Password Blocking:** Prevents users from choosing weak passwords that could be guessed.