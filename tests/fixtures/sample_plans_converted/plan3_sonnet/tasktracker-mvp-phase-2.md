# TaskTracker MVP Phase 2: Authentication System

**Status:** Pending
**Master Plan:** [tasktracker-mvp-MASTER_PLAN.md](tasktracker-mvp-MASTER_PLAN.md)
**Depends On:** [Phase 1: Data Layer Foundation](tasktracker-mvp-phase-1.md)

---

## Process Wrapper (MANDATORY)
- [ ] Read previous notes: `notes/NOTES_tasktracker_phase_1.md`
- [ ] **[IMPLEMENTATION - see Tasks below]**
- [ ] Pre-validation (ALL required):
  ```bash
  # Code quality
  npm run lint --fix
  npm run test
  npm audit
  ```
- [ ] Fix loop: repeat pre-validation until clean
- [ ] Write `notes/NOTES_tasktracker_phase_2.md` (REQUIRED)

## Gates (must pass before completion)

**ALL gates are BLOCKING.**

- lint: `npm run lint` - 0 errors
- tests: `npm test` - All tests pass (>85% coverage for auth code)
- security: `npm audit` - No high or critical severity issues

---

## Overview

Implement user registration, login, and JWT-based authentication. This phase builds on the User model from Phase 1 and provides the security foundation for the application. We'll create password hashing with bcrypt, JWT token generation/verification, authentication middleware, and secure endpoints for registration and login.

## Dependencies
- Previous phase: [Phase 1: Data Layer Foundation](tasktracker-mvp-phase-1.md) - requires User model and UserRepository
- External: bcryptjs, jsonwebtoken, supertest (dev)

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| JWT secret exposed or weak | Low | High | Generate strong secret with openssl, use env vars, never commit secrets |
| Password storage vulnerability | Low | High | Use bcrypt with >=10 salt rounds, validate with security tests |
| Token expiration issues | Medium | Medium | Use reasonable expiry (7d), handle expiration errors gracefully |
| Password complexity too weak | Medium | Medium | Enforce strong requirements (8+ chars, upper/lower/number), validate on server |
| Authentication bypass | Low | High | Comprehensive middleware tests, verify protection on all routes |

---

## Tasks

### 1. Install Dependencies & Configuration
- [ ] 1.1: Install `bcryptjs`, `jsonwebtoken`
- [ ] 1.2: Install dev dependency `supertest` for API testing
- [ ] 1.3: Create `src/config/auth.js` with JWT and bcrypt configuration
- [ ] 1.4: Add JWT_SECRET, JWT_EXPIRES_IN, BCRYPT_SALT_ROUNDS to `.env.example`
- [ ] 1.5: Document secret generation in README (openssl rand -base64 32)

### 2. Password Service
- [ ] 2.1: Create `src/services/PasswordService.js`
- [ ] 2.2: Implement `hash(password)` method using bcryptjs
- [ ] 2.3: Implement `compare(password, hash)` method
- [ ] 2.4: Implement `validate(password)` method with complexity rules
- [ ] 2.5: Define password requirements (min 8 chars, uppercase, lowercase, number)
- [ ] 2.6: Write unit tests in `tests/services/PasswordService.test.js`

### 3. Token Service
- [ ] 3.1: Create `src/services/TokenService.js`
- [ ] 3.2: Implement `generate(user)` method to create JWT tokens
- [ ] 3.3: Implement `verify(token)` method to validate and decode tokens
- [ ] 3.4: Implement `decode(token)` method for debugging (no verification)
- [ ] 3.5: Define token payload structure (userId, email, iat, exp)
- [ ] 3.6: Write unit tests in `tests/services/TokenService.test.js`

### 4. Authentication Controller
- [ ] 4.1: Create `src/controllers/AuthController.js`
- [ ] 4.2: Implement `register(req, res)` endpoint logic
- [ ] 4.3: Implement `login(req, res)` endpoint logic
- [ ] 4.4: Implement `getCurrentUser(req, res)` endpoint logic
- [ ] 4.5: Implement `changePassword(req, res)` endpoint logic
- [ ] 4.6: Add proper error handling for all methods
- [ ] 4.7: Write integration tests in `tests/auth/AuthController.test.js`

### 5. Authentication Middleware
- [ ] 5.1: Create `src/middleware/auth.js`
- [ ] 5.2: Implement `authenticate(req, res, next)` middleware
- [ ] 5.3: Extract token from Authorization header (Bearer format)
- [ ] 5.4: Verify token and attach user to req.user
- [ ] 5.5: Implement `optionalAuth(req, res, next)` for optional authentication
- [ ] 5.6: Write middleware tests in `tests/middleware/auth.test.js`

### 6. Input Validation Middleware
- [ ] 6.1: Create `src/middleware/validation.js`
- [ ] 6.2: Implement `validateRegistration(req, res, next)` middleware
- [ ] 6.3: Validate email format, username format, password complexity
- [ ] 6.4: Implement `validateLogin(req, res, next)` middleware
- [ ] 6.5: Return clear, helpful error messages for validation failures
- [ ] 6.6: Write validation tests

### 7. Error Handling
- [ ] 7.1: Create `src/middleware/errorHandler.js`
- [ ] 7.2: Define `AuthError` class extending Error with statusCode
- [ ] 7.3: Implement centralized error handler middleware
- [ ] 7.4: Handle different error types (400, 401, 403, 409, 500)
- [ ] 7.5: Log errors without exposing sensitive data
- [ ] 7.6: Write error handling tests

### 8. Routes Configuration
- [ ] 8.1: Create `src/routes/auth.js`
- [ ] 8.2: Define POST /register route (public)
- [ ] 8.3: Define POST /login route (public)
- [ ] 8.4: Define GET /me route (protected with authenticate middleware)
- [ ] 8.5: Define POST /change-password route (protected)
- [ ] 8.6: Apply validation middleware to appropriate routes

### 9. Integration Testing
- [ ] 9.1: Test registration endpoint: valid registration, duplicate email/username, invalid email, weak password
- [ ] 9.2: Test login endpoint: valid credentials, invalid email, invalid password, token generation
- [ ] 9.3: Test authentication middleware: valid token, missing token, invalid token, expired token
- [ ] 9.4: Test getCurrentUser endpoint: returns user data, password not included
- [ ] 9.5: Test changePassword endpoint: valid change, invalid current password, weak new password

### 10. Security Testing
- [ ] 10.1: Verify passwords are hashed (never stored plain text)
- [ ] 10.2: Verify passwords are never logged or returned in responses
- [ ] 10.3: Verify JWT secret is not hardcoded
- [ ] 10.4: Verify tokens expire as configured
- [ ] 10.5: Verify bcrypt salt rounds >= 10
- [ ] 10.6: Run `npm audit` and fix any vulnerabilities

---

## Files to Create/Modify

| File | Action | Purpose |
|------|--------|---------|
| `src/config/auth.js` | Create | JWT and bcrypt configuration |
| `src/services/PasswordService.js` | Create | Password hashing and validation |
| `src/services/TokenService.js` | Create | JWT token generation and verification |
| `src/controllers/AuthController.js` | Create | Registration and login logic |
| `src/middleware/auth.js` | Create | JWT authentication middleware |
| `src/middleware/validation.js` | Create | Input validation middleware |
| `src/middleware/errorHandler.js` | Create | Centralized error handling |
| `src/routes/auth.js` | Create | Authentication route definitions |
| `tests/services/PasswordService.test.js` | Create | Password service unit tests |
| `tests/services/TokenService.test.js` | Create | Token service unit tests |
| `tests/auth/AuthController.test.js` | Create | Auth controller integration tests |
| `tests/middleware/auth.test.js` | Create | Auth middleware tests |
| `.env.example` | Modify | Add JWT_SECRET, JWT_EXPIRES_IN, BCRYPT_SALT_ROUNDS |
| `README.md` | Modify | Add authentication setup documentation |

## Patterns to Follow

| Pattern | Reference | Usage |
|---------|-----------|-------|
| Service Layer | `src/services/` | Separate business logic from controllers |
| Middleware Chain | Express middleware | Compose validation -> auth -> controller |
| Error Classes | `AuthError` class | Custom errors with status codes for consistent handling |
| JWT Bearer Format | RFC 6750 | `Authorization: Bearer <token>` header format |
| Async Error Handling | Express async | Wrap async routes to catch errors properly |

## Test Strategy

- [ ] Unit tests for PasswordService: hashing produces different output with salt, compare matches correctly, validation catches weak passwords
- [ ] Unit tests for TokenService: generated tokens can be verified, expired tokens throw error, invalid tokens throw error
- [ ] Integration tests for registration: valid registration creates user, duplicate email/username returns 409, invalid input returns 400
- [ ] Integration tests for login: valid credentials return token, invalid credentials return 401, token can access protected routes
- [ ] Middleware tests: valid token allows access, missing/invalid/expired token returns 401, user attached to request
- [ ] Security tests: passwords never logged, hashes never returned, JWT secret not hardcoded, sufficient bcrypt rounds

## Validation

- Use `python-task-validator` to verify code quality and security patterns

## Acceptance Criteria

**ALL must pass:**

- [ ] All tasks completed
- [ ] All gates passing (lint, tests, security)
- [ ] Unit tests achieve >90% coverage for services
- [ ] Integration tests achieve >85% coverage for controllers
- [ ] Users can register with email, username, and password
- [ ] Users can log in and receive JWT token
- [ ] Protected routes require valid token
- [ ] Password change functionality works
- [ ] Passwords are hashed with bcrypt (>=10 rounds)
- [ ] JWT tokens use strong secret from env vars
- [ ] Tokens expire after configured time (7d)
- [ ] Password complexity requirements enforced
- [ ] No sensitive data in responses or logs
- [ ] Documentation complete with security guidelines

## Rollback Plan

If authentication system has critical issues:
1. Revert commits related to Phase 2
2. Remove authentication routes from Express app
3. Remove auth dependencies: `npm uninstall bcryptjs jsonwebtoken`
4. Drop User collection if passwords were compromised: `db.users.drop()`
5. Regenerate JWT secret and update environment variables
6. Re-run Phase 1 tests to ensure data layer still works

For production (if already deployed):
1. Take application offline (maintenance mode)
2. Backup User collection before any changes
3. Rotate JWT secret to invalidate all tokens
4. Force password reset for all users if hashing was compromised
5. Apply fix and redeploy
6. Notify users of security incident if necessary

---

## Implementation Notes

### Password Requirements
- Minimum 8 characters
- At least one uppercase letter
- At least one lowercase letter
- At least one number
- Optional: special character, max length (100)
- Consider checking against common password list

### JWT Token Payload Example
```javascript
{
  userId: '507f1f77bcf86cd799439011',
  email: 'user@example.com',
  iat: 1234567890,  // Issued at timestamp
  exp: 1235172690   // Expiration timestamp (7 days later)
}
```

### Authorization Header Format
```
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

### Security Best Practices
- Generate JWT_SECRET with: `openssl rand -base64 32`
- Never commit secrets to version control
- Use HTTPS only in production
- Implement rate limiting on auth endpoints (future enhancement)
- Consider refresh token pattern for longer sessions (future enhancement)
- Log authentication failures for security monitoring

### Error Response Format
```javascript
{
  success: false,
  error: 'Invalid credentials',
  statusCode: 401
}
```