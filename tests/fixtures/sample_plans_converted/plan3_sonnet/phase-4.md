# TaskTracker MVP Phase 4: React Frontend UI

**Status:** Pending
**Master Plan:** [TaskTracker MVP - Master Plan](MASTER_PLAN.md)
**Depends On:** [Phase 3: Task API Endpoints](phase-3.md)

---

## Process Wrapper (MANDATORY)

- [ ] Review previous notes: `notes/NOTES_phase3_task_api.md`
- [ ] Initialize React project: `npm create vite@latest tasktracker-ui -- --template react && cd tasktracker-ui`
- [ ] Install UI dependencies: `npm install @mui/material @mui/icons-material @emotion/react @emotion/styled @tanstack/react-query axios zustand react-router-dom react-hook-form date-fns`
- [ ] **[IMPLEMENTATION - see Tasks below]**
- [ ] Pre-validation (ALL required):
  ```bash
  # Code quality and testing
  npm run lint --fix
  npm run type-check
  npm test -- --coverage
  ```
- [ ] Fix loop: repeat pre-validation until clean
- [ ] Write `notes/NOTES_phase4_frontend_ui.md` (REQUIRED)

## Gates (must pass before completion)

**ALL gates are BLOCKING.**

- lint: 0 errors
- type-check: All types valid
- tests: All component tests pass
- coverage: >70% coverage on components
- responsive: Mobile, tablet, desktop layouts work
- accessibility: WCAG 2.1 AA compliance

---

## Overview

Build the React frontend application with Material-UI components. This phase creates a responsive, intuitive interface for task management with real-time feedback, smooth interactions, and complete integration with the backend API. Includes authentication pages, dashboard with task list, task CRUD operations, filtering and search, responsive design, and component tests.

## Dependencies
- Previous phase: Phase 3 (REST API endpoints)
- External: React, Vite, Material-UI, React Query, Zustand, React Router, React Hook Form, date-fns

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Frontend state management becomes complex | Medium | Medium | Use React Query for server state, Zustand for auth, keep local state minimal |
| API integration issues | Medium | Medium | Create comprehensive API service layer, thorough integration tests, Postman testing |
| Responsive design breaks on some devices | Low | Medium | Test on multiple breakpoints, use Material-UI responsive features, manual testing |
| Performance issues with large task lists | Low | Medium | Implement pagination, virtualization for very large lists, performance profiling |
| CORS errors in development | Low | Low | Configure backend CORS correctly, use proxy in dev if needed |

---

## Tasks

### 1. Project Setup & Configuration

- [ ] 1.1: Create React project with Vite: `npm create vite@latest tasktracker-ui -- --template react`
- [ ] 1.2: Install UI framework and dependencies
- [ ] 1.3: Create project structure:
  - [ ] `src/components/` (auth, tasks, layout, common)
  - [ ] `src/pages/` (Login, Register, Dashboard, NotFound)
  - [ ] `src/services/` (api, auth, tasks)
  - [ ] `src/hooks/` (useAuth, useTasks)
  - [ ] `src/store/` (authStore)
  - [ ] `src/utils/` (formatters, constants)
- [ ] 1.4: Configure Vite environment variables in `.env.example`
- [ ] 1.5: Set up ESLint and Prettier configuration
- [ ] 1.6: Configure testing with Vitest and React Testing Library
- [ ] 1.7: Create `.env.example` with API base URL

### 2. API Service Layer

- [ ] 2.1: Create `src/services/api.js` with Axios instance
- [ ] 2.2: Configure base URL from environment variable
- [ ] 2.3: Add request interceptor to attach JWT token to headers
- [ ] 2.4: Add response interceptor to handle 401 (logout on invalid token)
- [ ] 2.5: Handle network errors gracefully
- [ ] 2.6: Create `src/services/auth.js` with auth API methods:
  - [ ] `register(email, username, password)` - POST /auth/register
  - [ ] `login(email, password)` - POST /auth/login
  - [ ] `getCurrentUser()` - GET /auth/me
  - [ ] `logout()` - Clear token from storage
  - [ ] `isAuthenticated()` - Check if token exists
- [ ] 2.7: Create `src/services/tasks.js` with task API methods:
  - [ ] `getTasks(filters)` - GET /tasks with query params
  - [ ] `getTask(id)` - GET /tasks/:id
  - [ ] `createTask(taskData)` - POST /tasks
  - [ ] `updateTask(id, updates)` - PUT /tasks/:id
  - [ ] `deleteTask(id)` - DELETE /tasks/:id
  - [ ] `markComplete(id)` - POST /tasks/:id/complete
  - [ ] `getStats()` - GET /tasks/stats
  - [ ] `searchTasks(query)` - GET /tasks/search

### 3. Authentication Pages

- [ ] 3.1: Create `src/pages/Login.jsx` page:
  - [ ] Email and password input fields
  - [ ] Form validation using react-hook-form
  - [ ] Login button and loading state
  - [ ] Error message display
  - [ ] Link to register page
  - [ ] On success, navigate to dashboard and store token
- [ ] 3.2: Create `src/pages/Register.jsx` page:
  - [ ] Email, username, password, confirm password fields
  - [ ] Form validation (email format, username rules, password strength)
  - [ ] Register button and loading state
  - [ ] Error message display
  - [ ] Link to login page
  - [ ] Password strength indicator
  - [ ] On success, redirect to login or auto-login
- [ ] 3.3: Create `src/components/auth/PrivateRoute.jsx` component:
  - [ ] Check if user is authenticated
  - [ ] Redirect to login if not authenticated
  - [ ] Render protected component if authenticated
- [ ] 3.4: Add form validation and error messages
- [ ] 3.5: Add loading states and disabled buttons during submission

### 4. Authentication State Management

- [ ] 4.1: Create `src/store/authStore.js` using Zustand:
  - [ ] Store user data (email, username, userId)
  - [ ] Store authentication token
  - [ ] Actions: login, logout, setUser, setToken
  - [ ] Persist token to localStorage
- [ ] 4.2: Create `src/hooks/useAuth.js` custom hook:
  - [ ] Access auth state from Zustand
  - [ ] Provide login, logout, getCurrentUser functions
  - [ ] Handle loading and error states
- [ ] 4.3: Initialize auth state on app startup:
  - [ ] Load token from localStorage
  - [ ] Verify token is still valid
  - [ ] Restore user data if token valid

### 5. Layout Components

- [ ] 5.1: Create `src/components/layout/Layout.jsx` main layout:
  - [ ] Fixed app bar with TaskTracker title
  - [ ] Navigation drawer (sidebar)
  - [ ] Main content area
  - [ ] Logout button
- [ ] 5.2: Create `src/components/layout/AppBar.jsx`:
  - [ ] Menu button to toggle drawer
  - [ ] Title display
  - [ ] User menu (settings, logout)
  - [ ] Dark/light theme toggle (optional)
- [ ] 5.3: Create `src/components/layout/Sidebar.jsx`:
  - [ ] Navigation links
  - [ ] Quick filters
  - [ ] Task statistics
  - [ ] Settings link

### 6. Task List & Display Components

- [ ] 6.1: Create `src/components/tasks/TaskList.jsx` component:
  - [ ] Use React Query to fetch tasks
  - [ ] Handle loading state (skeleton cards)
  - [ ] Handle error state with error message
  - [ ] Display tasks in grid layout
  - [ ] Show "no tasks" message if empty
  - [ ] Integrate with filters
- [ ] 6.2: Create `src/components/tasks/TaskCard.jsx` component:
  - [ ] Display task title, description
  - [ ] Show status badge with color coding
  - [ ] Show priority chip with color coding
  - [ ] Display due date if present
  - [ ] Action buttons (complete, edit, delete)
  - [ ] Show tags if present
  - [ ] Responsive card design
- [ ] 6.3: Create `src/components/tasks/TaskStats.jsx` component:
  - [ ] Display task counts by status
  - [ ] Display task counts by priority
  - [ ] Show overdue task count
  - [ ] Use React Query to fetch stats
  - [ ] Update when tasks change

### 7. Task Form & Dialog Components

- [ ] 7.1: Create `src/components/tasks/TaskForm.jsx` dialog component:
  - [ ] Form for creating and editing tasks
  - [ ] Title input (required)
  - [ ] Description textarea
  - [ ] Status select dropdown
  - [ ] Priority select dropdown
  - [ ] Due date picker (date-fns)
  - [ ] Tags input
  - [ ] Save and cancel buttons
  - [ ] Form validation using react-hook-form
  - [ ] Loading state during submission
- [ ] 7.2: Create dialog trigger button in TaskList
- [ ] 7.3: Pre-fill form when editing existing task
- [ ] 7.4: On save, invalidate React Query cache to refresh list

### 8. Task Filtering & Search Components

- [ ] 8.1: Create `src/components/tasks/TaskFilters.jsx` component:
  - [ ] Status checkboxes (todo, in_progress, done)
  - [ ] Priority checkboxes (low, medium, high)
  - [ ] Search input for title/description
  - [ ] Sort dropdown (created, dueDate, priority)
  - [ ] Clear all filters button
  - [ ] Apply filters on change
- [ ] 8.2: Manage filter state using React hooks
- [ ] 8.3: Pass filters to TaskList component
- [ ] 8.4: Update URL query parameters when filters change (optional, for bookmarking)

### 9. Common Components

- [ ] 9.1: Create `src/components/common/Loading.jsx`:
  - [ ] Skeleton card loaders during data fetch
  - [ ] Spinner for action loading states
- [ ] 9.2: Create `src/components/common/ErrorMessage.jsx`:
  - [ ] Display error messages from API
  - [ ] User-friendly error descriptions
  - [ ] Retry button if applicable
- [ ] 9.3: Create `src/components/common/ConfirmDialog.jsx`:
  - [ ] Confirmation dialog for delete actions
  - [ ] Custom message text
  - [ ] Confirm/cancel buttons
- [ ] 9.4: Create `src/components/common/EmptyState.jsx`:
  - [ ] Empty state message
  - [ ] Icon and helpful text
  - [ ] Action button (e.g., "Create task")

### 10. Dashboard Page

- [ ] 10.1: Create `src/pages/Dashboard.jsx` page:
  - [ ] Render Layout component as wrapper
  - [ ] Render TaskStats component
  - [ ] Render TaskFilters component
  - [ ] Render TaskList component
  - [ ] Button to create new task
  - [ ] Handle loading and error states
- [ ] 10.2: Manage filter state in Dashboard
- [ ] 10.3: Pass filters to TaskList

### 11. React Router Configuration

- [ ] 11.1: Create `src/App.jsx` with route definitions:
  - [ ] `POST /login` - LoginForm page (public)
  - [ ] `POST /register` - RegisterForm page (public)
  - [ ] `GET /dashboard` - Dashboard page (protected)
  - [ ] `GET /` - Redirect to dashboard
  - [ ] 404 handler for invalid routes
- [ ] 11.2: Configure QueryClientProvider for React Query
- [ ] 11.3: Configure ThemeProvider for Material-UI
- [ ] 11.4: Set up Router with BrowserRouter

### 12. Material-UI Theme Configuration

- [ ] 12.1: Create custom Material-UI theme in `src/theme.js`:
  - [ ] Primary color (blue)
  - [ ] Secondary color (teal)
  - [ ] Typography settings
  - [ ] Spacing and breakpoints
- [ ] 12.2: Configure theme provider
- [ ] 12.3: Apply theme consistently across components

### 13. Responsive Design

- [ ] 13.1: Mobile (xs < 600px):
  - [ ] Single column layout
  - [ ] Full-width cards
  - [ ] Hamburger menu for drawer
  - [ ] Bottom sheet for filters
- [ ] 13.2: Tablet (sm, md: 600px - 1200px):
  - [ ] Two column grid for tasks
  - [ ] Collapsible sidebar
  - [ ] Medium-sized cards
- [ ] 13.3: Desktop (lg, xl > 1200px):
  - [ ] Three column grid for tasks
  - [ ] Persistent sidebar
  - [ ] Full-featured layout
- [ ] 13.4: Test on actual devices and breakpoints
- [ ] 13.5: Use Material-UI sx prop for responsive styles

### 14. Component Testing

- [ ] 14.1: Create `tests/components/Login.test.jsx`:
  - [ ] Form validates required fields
  - [ ] Email validation works
  - [ ] Submit calls API
  - [ ] Error messages display
- [ ] 14.2: Create `tests/components/TaskCard.test.jsx`:
  - [ ] Displays task data correctly
  - [ ] Shows correct status/priority colors
  - [ ] Action buttons work
- [ ] 14.3: Create `tests/components/TaskList.test.jsx`:
  - [ ] Displays tasks from API
  - [ ] Shows loading state
  - [ ] Shows error message
  - [ ] Shows empty state
- [ ] 14.4: Create `tests/components/TaskForm.test.jsx`:
  - [ ] Form validates required fields
  - [ ] Submit creates task
  - [ ] Submit updates task
- [ ] 14.5: Aim for >70% component coverage

### 15. Integration Testing

- [ ] 15.1: Test login flow end-to-end
- [ ] 15.2: Test task creation and display
- [ ] 15.3: Test task editing and update
- [ ] 15.4: Test task deletion
- [ ] 15.5: Test filtering updates display
- [ ] 15.6: Test search finds tasks
- [ ] 15.7: Test logout clears state

### 16. Performance Optimization

- [ ] 16.1: Lazy load pages with React.lazy
- [ ] 16.2: Memoize expensive components
- [ ] 16.3: Optimize images and assets
- [ ] 16.4: Configure React Query caching strategy
- [ ] 16.5: Profile with React DevTools

### 17. Offline Support (Basic)

- [ ] 17.1: Detect offline state
- [ ] 17.2: Show offline banner
- [ ] 17.3: Queue mutations when offline
- [ ] 17.4: Sync when back online (optional)

### 18. Documentation

- [ ] 18.1: Create `docs/FRONTEND.md` with:
  - [ ] Project setup instructions
  - [ ] Architecture overview
  - [ ] Component documentation
  - [ ] State management explanation
  - [ ] API integration guide
  - [ ] Development workflow
- [ ] 18.2: Add JSDoc comments to components
- [ ] 18.3: Document component props
- [ ] 18.4: Create user guide for application

---

## Files to Create/Modify

| File | Action | Purpose |
|------|--------|---------|
| `src/App.jsx` | Create | Root application with routing |
| `src/main.jsx` | Create | React entry point |
| `src/services/api.js` | Create | Axios instance with interceptors |
| `src/services/auth.js` | Create | Authentication API methods |
| `src/services/tasks.js` | Create | Task API methods |
| `src/store/authStore.js` | Create | Zustand auth store |
| `src/hooks/useAuth.js` | Create | Auth custom hook |
| `src/theme.js` | Create | Material-UI theme configuration |
| `src/pages/Login.jsx` | Create | Login page |
| `src/pages/Register.jsx` | Create | Register page |
| `src/pages/Dashboard.jsx` | Create | Dashboard page |
| `src/components/layout/Layout.jsx` | Create | Main layout wrapper |
| `src/components/layout/AppBar.jsx` | Create | Top application bar |
| `src/components/layout/Sidebar.jsx` | Create | Sidebar navigation |
| `src/components/auth/PrivateRoute.jsx` | Create | Route protection component |
| `src/components/tasks/TaskList.jsx` | Create | Task list display |
| `src/components/tasks/TaskCard.jsx` | Create | Individual task card |
| `src/components/tasks/TaskForm.jsx` | Create | Create/edit task form |
| `src/components/tasks/TaskFilters.jsx` | Create | Filter controls |
| `src/components/tasks/TaskStats.jsx` | Create | Task statistics display |
| `src/components/common/Loading.jsx` | Create | Loading skeleton/spinner |
| `src/components/common/ErrorMessage.jsx` | Create | Error display component |
| `src/components/common/ConfirmDialog.jsx` | Create | Confirmation dialog |
| `src/components/common/EmptyState.jsx` | Create | Empty state display |
| `tests/components/Login.test.jsx` | Create | Login component tests |
| `tests/components/TaskCard.test.jsx` | Create | TaskCard component tests |
| `tests/components/TaskList.test.jsx` | Create | TaskList component tests |
| `tests/components/TaskForm.test.jsx` | Create | TaskForm component tests |
| `docs/FRONTEND.md` | Create | Frontend documentation |
| `vite.config.js` | Create | Vite configuration |
| `.env.example` | Create | Environment variables template |
| `package.json` | Modify | Add all dependencies |

## Patterns to Follow

| Pattern | Reference | Usage |
|---------|-----------|-------|
| Custom Hooks | `useAuth`, `useTasks` | Encapsulate state logic, enable reuse across components |
| React Query | Service layer + TanStack | Server state management, caching, invalidation |
| State Management | Zustand | Simple global state for auth, avoid prop drilling |
| Protected Routes | `PrivateRoute` | Gate dashboard and task pages from unauthenticated users |
| Component Composition | Common components | Build complex UIs from reusable pieces |
| Responsive Design | sx prop + breakpoints | Mobile-first approach with Material-UI |

## Test Strategy

- [ ] Unit tests for components (rendering, props, events)
- [ ] Integration tests for flows (login → dashboard → create task)
- [ ] API mocking with mock API responses
- [ ] Snapshot tests for layout consistency
- [ ] Manual testing on mobile, tablet, desktop devices
- [ ] Accessibility testing (keyboard nav, screen readers)
- [ ] Performance profiling and optimization

## Acceptance Criteria

**ALL must pass:**

- [ ] Users can log in and register
- [ ] Dashboard displays authenticated user's tasks
- [ ] Tasks can be created, edited, deleted
- [ ] Filters update displayed tasks
- [ ] Search finds tasks by title/description
- [ ] Responsive on mobile, tablet, desktop
- [ ] Loading states during async operations
- [ ] Error messages are helpful and clear
- [ ] Smooth transitions and animations
- [ ] Keyboard navigation works
- [ ] All component tests pass (>70% coverage)
- [ ] Integration tests pass
- [ ] ESLint passes with 0 errors
- [ ] API integration successful
- [ ] Frontend successfully calls all endpoints
- [ ] Authentication tokens work correctly
- [ ] Error responses handled properly
- [ ] Pagination works with large datasets
- [ ] No console errors or warnings

## Rollback Plan

If Phase 4 encounters critical issues:

1. **API integration failures:**
   - Verify API is running and accessible
   - Check CORS configuration
   - Review API response format
   - Test with Postman before debugging frontend
   - Check browser network tab for actual API responses

2. **React Query issues:**
   - Verify QueryClient is configured
   - Check cache invalidation logic
   - Ensure API service returns expected format
   - Review React Query devtools

3. **Authentication issues:**
   - Verify token is stored in localStorage
   - Check axios interceptor logic
   - Test API token validation with Postman
   - Review auth middleware on backend

4. **Component rendering issues:**
   - Check React DevTools for component tree
   - Verify props are passed correctly
   - Check for infinite loops in useEffect
   - Review Material-UI documentation

5. **Build/bundling issues:**
   - Clear Vite cache: `rm -rf node_modules/.vite`
   - Reinstall dependencies: `rm -rf node_modules && npm install`
   - Check Vite config for correct settings
   - Verify environment variables are loaded

6. **Complete rollback:**
   - Delete React project and start fresh
   - Ensure backend API is running first
   - Verify all API endpoints with Postman
   - Create new React project and rebuild incrementally

---

## Implementation Notes

This phase implements the complete user interface for task management. Key architectural decisions:

1. **React Query for Server State:** Centralized caching and invalidation reduces complexity and prevents data synchronization bugs.

2. **Zustand for Auth State:** Lightweight store keeps auth state simple without Redux boilerplate. Persists to localStorage for session recovery.

3. **Material-UI for Consistency:** Pre-built components with built-in responsive design, theming, and accessibility features accelerate development.

4. **Custom Hooks for Logic Reuse:** useAuth and useTasks encapsulate API/state logic, making components focused on UI concerns.

5. **Mobile-First Responsive Design:** Start with mobile constraints then add responsive features for larger screens using Material-UI breakpoints.