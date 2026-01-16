# TaskTracker MVP Phase 4: User Interface Module

**Status:** Pending
**Master Plan:** [TaskTracker MVP - Master Plan](MASTER_PLAN.md)
**Depends On:** [Phase 3: Task API Module](tasktracker-phase-3.md)

---

## Process Wrapper (MANDATORY)
- [ ] Read previous notes: `notes/NOTES_phase_3_api.md`
- [ ] Verify Phases 1, 2, and 3 are complete and all gates passing
- [ ] Verify backend API is running and all endpoints tested with Postman
- [ ] **[IMPLEMENTATION - see Tasks below]**
- [ ] Pre-validation (ALL required):
  ```bash
  npm run lint --fix
  npm run type-check
  npm test
  npm run build
  ```
- [ ] Fix loop: repeat pre-validation until clean
- [ ] Write `notes/NOTES_phase_4_ui.md` (REQUIRED)

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
- tests: All tests pass (>70% coverage)
  ```bash
  command: npm test -- --coverage
  ```
- security: No high severity issues
  ```bash
  command: npm audit
  ```
- build: Production build succeeds
  ```bash
  command: npm run build
  ```

---

## Overview

Build the React frontend application with Material-UI components. This phase creates a responsive, intuitive interface for task management with real-time feedback and smooth interactions. The frontend must integrate seamlessly with the Phase 3 API and provide an excellent user experience across mobile, tablet, and desktop devices.

## Dependencies
- Previous phase: [Phase 3: Task API Module](tasktracker-phase-3.md) - requires fully functional backend API
- External: React, Vite, Material-UI, React Query, React Router, React Hook Form, Axios

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Frontend/backend API contract drift | Medium | High | Keep API documentation updated, test endpoints before UI implementation, use TypeScript |
| React Query caching causes stale data | Low | Medium | Configure cache invalidation on mutations, implement manual refetch where needed |
| Responsive design breaks on edge cases | Medium | Medium | Test on actual devices (or browser DevTools), use Material-UI Grid system, test breakpoints |
| State management becomes complex | Medium | Medium | Use React Query for server state, Zustand for auth state, keep local state minimal |
| Token refresh not handled properly | Low | High | Implement axios interceptor for 401 responses, test token expiration scenario |

---

## Tasks

### 1. Project Setup and Configuration
- [ ] 1.1: Initialize React project with Vite: `npm create vite@latest tasktracker-ui -- --template react`
- [ ] 1.2: Install dependencies (Material-UI, React Query, React Router, React Hook Form, Axios, date-fns)
- [ ] 1.3: Create project structure (components/, pages/, services/, hooks/, store/, utils/)
- [ ] 1.4: Configure environment variables (.env.example with VITE_API_URL)
- [ ] 1.5: Create Vite config with proper frontend dev server settings
- [ ] 1.6: Set up ESLint and Prettier for code formatting

### 2. API Service Layer
- [ ] 2.1: Create `src/services/api.js` with Axios instance
- [ ] 2.2: Implement request interceptor to add auth token from localStorage
- [ ] 2.3: Implement response interceptor to handle 401 (logout on token expiration)
- [ ] 2.4: Create `src/services/auth.js` with register, login, getCurrentUser, logout
- [ ] 2.5: Create `src/services/tasks.js` with getTasks, getTask, createTask, updateTask, deleteTask, markComplete, getStats, searchTasks
- [ ] 2.6: Test all service methods with backend API

### 3. Authentication Pages and Components
- [ ] 3.1: Create `src/pages/Login.jsx` with email and password form
- [ ] 3.2: Create `src/pages/Register.jsx` with email, username, password fields
- [ ] 3.3: Create `src/components/auth/PrivateRoute.jsx` for protected routes
- [ ] 3.4: Implement form validation with react-hook-form
- [ ] 3.5: Implement error handling and user feedback (success/error messages)
- [ ] 3.6: Test login and register flows end-to-end with backend
- [ ] 3.7: Test password validation rules are enforced
- [ ] 3.8: Test token is stored and used for subsequent requests

### 4. Layout and Navigation Components
- [ ] 4.1: Create `src/components/layout/Layout.jsx` with AppBar and Drawer
- [ ] 4.2: Implement logout button and functionality
- [ ] 4.3: Create `src/components/layout/AppBar.jsx` with title and user menu
- [ ] 4.4: Create `src/components/layout/Sidebar.jsx` for filters and navigation
- [ ] 4.5: Implement responsive navigation (hamburger menu on mobile)
- [ ] 4.6: Style components with Material-UI theme

### 5. Task List and Card Components
- [ ] 5.1: Create `src/components/tasks/TaskList.jsx` to display tasks in grid
- [ ] 5.2: Create `src/components/tasks/TaskCard.jsx` to show individual task
- [ ] 5.3: Implement React Query integration for data fetching
- [ ] 5.4: Implement loading states with skeleton screens
- [ ] 5.5: Implement error handling with error messages
- [ ] 5.6: Implement empty state when no tasks found
- [ ] 5.7: Add action buttons (edit, delete, complete) to task cards
- [ ] 5.8: Implement task completion with visual feedback

### 6. Task Form and Filters
- [ ] 6.1: Create `src/components/tasks/TaskForm.jsx` (create/edit modal)
- [ ] 6.2: Implement title input (required), description textarea, status/priority selects
- [ ] 6.3: Implement due date picker with date-fns
- [ ] 6.4: Implement tags input field
- [ ] 6.5: Create `src/components/tasks/TaskFilters.jsx` with status, priority, search
- [ ] 6.6: Implement filter application and query parameter handling
- [ ] 6.7: Implement sort options (createdAt, dueDate, priority, title)
- [ ] 6.8: Implement clear filters button

### 7. Dashboard Page and Statistics
- [ ] 7.1: Create `src/pages/Dashboard.jsx` as main application page
- [ ] 7.2: Create `src/components/tasks/TaskStats.jsx` to show counts and metrics
- [ ] 7.3: Implement statistics fetching and display (count by status, priority, overdue)
- [ ] 7.4: Implement layout with sidebar filters and main task list
- [ ] 7.5: Implement responsive grid (1 column mobile, 2-3 columns desktop)

### 8. Application Setup and Routing
- [ ] 8.1: Create `src/App.jsx` with React Router configuration
- [ ] 8.2: Configure routes (/, /login, /register, /dashboard, 404 page)
- [ ] 8.3: Set up QueryClientProvider and ThemeProvider
- [ ] 8.4: Create Material-UI theme (colors, typography, spacing)
- [ ] 8.5: Implement private route protection
- [ ] 8.6: Implement 404 page for unknown routes

### 9. State Management and Hooks
- [ ] 9.1: Create `src/store/authStore.js` with Zustand for auth state (user, token, logout)
- [ ] 9.2: Create `src/hooks/useAuth.js` custom hook to access auth state
- [ ] 9.3: Create `src/hooks/useTasks.js` custom hook for task queries and mutations
- [ ] 9.4: Implement auth state persistence to localStorage
- [ ] 9.5: Implement auth state restoration on app load

### 10. Utility Functions and Helpers
- [ ] 10.1: Create `src/utils/formatters.js` with date, priority, status formatting helpers
- [ ] 10.2: Create `src/components/common/Loading.jsx` loading indicator
- [ ] 10.3: Create `src/components/common/ErrorMessage.jsx` error display
- [ ] 10.4: Create `src/components/common/ConfirmDialog.jsx` for delete confirmation
- [ ] 10.5: Implement consistent error handling across components

### 11. Responsive Design and Testing
- [ ] 11.1: Test layout on mobile (375px), tablet (768px), desktop (1440px) viewports
- [ ] 11.2: Test touch interactions on mobile devices
- [ ] 11.3: Test keyboard navigation and accessibility
- [ ] 11.4: Implement auto-scroll toggle for task list
- [ ] 11.5: Test orientation changes (portrait/landscape)

### 12. Testing and Documentation
- [ ] 12.1: Write component tests for Login, Register, TaskList, TaskCard
- [ ] 12.2: Write integration tests for auth flow, task CRUD, filtering
- [ ] 12.3: Write tests for all custom hooks
- [ ] 12.4: Achieve >70% test coverage for Phase 4
- [ ] 12.5: Create user guide documentation
- [ ] 12.6: Create deployment documentation for Vercel
- [ ] 12.7: Test production build with `npm run build`

---

## Files to Create/Modify

| File | Action | Purpose |
|------|--------|---------|
| `src/App.jsx` | Create | Main app component with routing and providers |
| `src/pages/Login.jsx` | Create | Login page with form |
| `src/pages/Register.jsx` | Create | Registration page with form |
| `src/pages/Dashboard.jsx` | Create | Main dashboard with task list and filters |
| `src/pages/NotFound.jsx` | Create | 404 page for unknown routes |
| `src/components/layout/Layout.jsx` | Create | Main layout wrapper with AppBar and Drawer |
| `src/components/layout/AppBar.jsx` | Create | Top navigation bar |
| `src/components/layout/Sidebar.jsx` | Create | Sidebar with filters and navigation |
| `src/components/tasks/TaskList.jsx` | Create | Task grid display |
| `src/components/tasks/TaskCard.jsx` | Create | Individual task card |
| `src/components/tasks/TaskForm.jsx` | Create | Create/edit task modal |
| `src/components/tasks/TaskFilters.jsx` | Create | Filter panel |
| `src/components/tasks/TaskStats.jsx` | Create | Statistics display |
| `src/components/auth/PrivateRoute.jsx` | Create | Protected route wrapper |
| `src/components/common/Loading.jsx` | Create | Loading indicator |
| `src/components/common/ErrorMessage.jsx` | Create | Error message display |
| `src/components/common/ConfirmDialog.jsx` | Create | Confirmation dialog |
| `src/services/api.js` | Create | Axios instance with interceptors |
| `src/services/auth.js` | Create | Auth API service |
| `src/services/tasks.js` | Create | Tasks API service |
| `src/hooks/useAuth.js` | Create | Auth state hook |
| `src/hooks/useTasks.js` | Create | Tasks data hook |
| `src/store/authStore.js` | Create | Zustand auth store |
| `src/utils/formatters.js` | Create | Utility formatting functions |
| `tests/` | Create | Component and integration tests |
| `.env.example` | Create | Environment variable template |
| `vite.config.js` | Create | Vite configuration |
| `package.json` | Modify | Add dependencies and scripts |

## Patterns to Follow

| Pattern | Reference | Usage |
|---------|-----------|-------|
| Container/Presentational | TaskList (container) / TaskCard (presentational) | Separate data fetching from UI rendering |
| Custom Hooks | useAuth, useTasks | Encapsulate state and logic for reusability |
| React Query | useQuery for GET, useMutation for POST/PUT/DELETE | Handle server state and caching |
| Zustand Store | authStore | Lightweight client-side state for auth |
| Error Boundaries | Try-catch in async handlers | Gracefully handle errors in components |
| Responsive Grid | Material-UI Grid with breakpoints | Adapt layout to screen size |

## Test Strategy

- [ ] Component tests for Login (form validation, error handling, successful login)
- [ ] Component tests for Register (form validation, password requirements, success)
- [ ] Component tests for TaskCard (display task data, action buttons, completion)
- [ ] Component tests for TaskList (displays tasks, loading state, empty state)
- [ ] Component tests for TaskFilters (filter application, sort options)
- [ ] Integration test for auth flow (register → login → access dashboard)
- [ ] Integration test for task CRUD (create → list → edit → delete)
- [ ] Integration test for filtering (apply filters, results update)
- [ ] Integration test for search (search finds tasks, empty results)
- [ ] Hook tests for useAuth (login, logout, getCurrentUser)
- [ ] Hook tests for useTasks (fetch, create, update, delete)
- [ ] Responsive design tests (mobile, tablet, desktop layouts)
- [ ] Accessibility tests (keyboard navigation, screen reader compatibility)

## Acceptance Criteria

**ALL must pass:**

- [ ] All tasks completed as specified
- [ ] All gates passing (lint, type-check, tests, security, build)
- [ ] Test coverage exceeds 70% for Phase 4
- [ ] Login page works correctly and authenticates users
- [ ] Register page creates new users with password validation
- [ ] Dashboard displays user's tasks correctly
- [ ] Tasks can be created via form
- [ ] Tasks can be edited with update modal
- [ ] Tasks can be deleted with confirmation
- [ ] Tasks can be marked complete with visual feedback
- [ ] Filtering works for status, priority, and search
- [ ] Sorting works for multiple fields
- [ ] Pagination displays correct number of tasks
- [ ] Layout is responsive on mobile, tablet, and desktop
- [ ] Error messages are helpful and user-friendly
- [ ] Loading states shown during async operations
- [ ] Token refresh handled on 401 responses
- [ ] Empty states displayed when no tasks exist
- [ ] Frontend integrates with all backend API endpoints
- [ ] Production build succeeds without errors
- [ ] Application can be deployed to Vercel

## Rollback Plan

If Phase 4 fails validation:
1. Reset to Phase 3 completion: `git reset --hard <phase_3_complete_commit>`
2. Review failed component tests in test output
3. Check API integration by manually testing with backend Postman collection
4. If API calls fail, verify VITE_API_URL is set correctly
5. If authentication fails, verify token is being stored/retrieved from localStorage
6. If responsive design tests fail, check Material-UI breakpoints and Grid configuration
7. If build fails, check for TypeScript errors: `npm run type-check`
8. Fix identified issues and re-run all gates
9. Test production build locally: `npm run build && npm run preview`
10. Manually test end-to-end flow (login, create task, edit, delete, filter, search) before declaring phase complete

---

## Implementation Notes

{To be filled during implementation}