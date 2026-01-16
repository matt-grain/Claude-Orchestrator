# TaskTracker MVP Phase 4: User Interface

**Status:** Pending
**Master Plan:** [tasktracker-mvp-MASTER_PLAN.md](tasktracker-mvp-MASTER_PLAN.md)
**Depends On:** [Phase 1: Data Layer Foundation](tasktracker-mvp-phase-1.md), [Phase 2: Authentication System](tasktracker-mvp-phase-2.md), [Phase 3: Task API Implementation](tasktracker-mvp-phase-3.md)

---

## Process Wrapper (MANDATORY)
- [ ] Read previous notes: `notes/NOTES_tasktracker_phase_1.md`, `notes/NOTES_tasktracker_phase_2.md`, `notes/NOTES_tasktracker_phase_3.md`
- [ ] **[IMPLEMENTATION - see Tasks below]**
- [ ] Pre-validation (ALL required):
  ```bash
  # Code quality
  npm run lint --fix
  npm run type-check  # if using TypeScript
  npm run test
  npm run build
  ```
- [ ] Fix loop: repeat pre-validation until clean
- [ ] Write `notes/NOTES_tasktracker_phase_4.md` (REQUIRED)

## Gates (must pass before completion)

**ALL gates are BLOCKING.**

- lint: `npm run lint` - 0 errors
- type-check: `npm run type-check` - 0 errors (if using TypeScript)
- tests: `npm run test` - All tests pass (>70% coverage for components)
- build: `npm run build` - Build succeeds, bundle size reasonable
- performance: Frontend loads within 1.5s on 4G connection

---

## Overview

Build the React frontend application with Material-UI components. This phase creates a responsive, intuitive interface for task management with real-time feedback and smooth interactions. The frontend will consume all API endpoints from Phase 3, handle authentication state, and provide excellent user experience on mobile, tablet, and desktop devices.

## Dependencies
- Previous phase: All backend phases complete (Phase 1, 2, 3)
- External: React, Material-UI, React Query, React Router, React Hook Form, date-fns, Vite

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Frontend state complexity | Medium | Medium | Use React Query for server state, minimize local state, clear patterns |
| API integration issues | Low | High | Test API calls thoroughly, handle all error responses, use Postman collection |
| Responsive design breaks on some devices | Medium | Low | Test on multiple devices/browsers, use Material-UI breakpoints, mobile-first |
| Performance issues with large task lists | Low | Medium | Implement pagination, virtualization if needed, optimize re-renders |
| Bundle size too large | Low | Low | Code splitting, tree shaking, monitor bundle size, lazy loading |

---

## Tasks

### 1. Project Setup
- [ ] 1.1: Initialize React project with Vite: `npm create vite@latest tasktracker-ui -- --template react`
- [ ] 1.2: Install UI dependencies: `@mui/material`, `@mui/icons-material`, `@emotion/react`, `@emotion/styled`
- [ ] 1.3: Install state/data dependencies: `@tanstack/react-query`, `axios`, `zustand`
- [ ] 1.4: Install routing: `react-router-dom`
- [ ] 1.5: Install forms: `react-hook-form`
- [ ] 1.6: Install date handling: `date-fns`
- [ ] 1.7: Install dev dependencies: `@testing-library/react`, `@testing-library/jest-dom`, `vitest`
- [ ] 1.8: Configure Vite, ESLint, and test environment
- [ ] 1.9: Create project structure: `components/`, `pages/`, `services/`, `hooks/`, `store/`, `utils/`

### 2. API Service Layer
- [ ] 2.1: Create `src/services/api.js` with Axios instance
- [ ] 2.2: Configure base URL from environment variable
- [ ] 2.3: Add request interceptor to attach JWT token
- [ ] 2.4: Add response interceptor to handle 401 errors (token expiration)
- [ ] 2.5: Create `src/services/auth.js` with authService (register, login, getCurrentUser, logout, isAuthenticated)
- [ ] 2.6: Create `src/services/tasks.js` with taskService (getTasks, getTask, createTask, updateTask, deleteTask, markComplete, getStats, searchTasks)
- [ ] 2.7: Test API services with backend running

### 3. Authentication Pages
- [ ] 3.1: Create `src/pages/Login.jsx` with login form
- [ ] 3.2: Implement form validation using react-hook-form
- [ ] 3.3: Handle login errors and display user-friendly messages
- [ ] 3.4: Redirect to dashboard on successful login
- [ ] 3.5: Create `src/pages/Register.jsx` with registration form
- [ ] 3.6: Add username, email, password, confirm password fields
- [ ] 3.7: Validate password complexity on frontend
- [ ] 3.8: Handle registration errors
- [ ] 3.9: Create `src/components/auth/PrivateRoute.jsx` for protected routes
- [ ] 3.10: Test authentication flows

### 4. Dashboard Layout
- [ ] 4.1: Create `src/components/layout/Layout.jsx` with app structure
- [ ] 4.2: Implement AppBar with logo, title, and logout button
- [ ] 4.3: Implement Drawer/Sidebar for filters and navigation
- [ ] 4.4: Make layout responsive (collapsible sidebar on mobile)
- [ ] 4.5: Create `src/components/layout/AppBar.jsx` component
- [ ] 4.6: Create `src/components/layout/Sidebar.jsx` component
- [ ] 4.7: Test layout on mobile, tablet, and desktop

### 5. Task List Components
- [ ] 5.1: Create `src/components/tasks/TaskList.jsx` with React Query integration
- [ ] 5.2: Fetch tasks using taskService.getTasks with filters
- [ ] 5.3: Display loading skeleton during fetch
- [ ] 5.4: Display error message on failure
- [ ] 5.5: Display "No tasks found" message for empty results
- [ ] 5.6: Create `src/components/tasks/TaskCard.jsx` for individual tasks
- [ ] 5.7: Display task title, description, status chip, priority chip, due date
- [ ] 5.8: Add action buttons: mark complete, edit, delete
- [ ] 5.9: Implement responsive grid layout (1 column mobile, 2 tablet, 3 desktop)
- [ ] 5.10: Test task list rendering with various datasets

### 6. Task Form Components
- [ ] 6.1: Create `src/components/tasks/TaskForm.jsx` as modal dialog
- [ ] 6.2: Implement form fields: title (required), description, status, priority, due date, tags
- [ ] 6.3: Use react-hook-form for form state management
- [ ] 6.4: Implement create task functionality
- [ ] 6.5: Implement edit task functionality (pre-fill form)
- [ ] 6.6: Add form validation (required fields, max lengths)
- [ ] 6.7: Handle form submission errors
- [ ] 6.8: Invalidate React Query cache on success to refresh list
- [ ] 6.9: Test create and edit flows

### 7. Task Filters & Search
- [ ] 7.1: Create `src/components/tasks/TaskFilters.jsx` component
- [ ] 7.2: Add status checkboxes (todo, in_progress, done)
- [ ] 7.3: Add priority checkboxes (low, medium, high)
- [ ] 7.4: Add search input with debouncing
- [ ] 7.5: Add sort dropdown (createdAt, dueDate, priority, title)
- [ ] 7.6: Add sort order toggle (asc/desc)
- [ ] 7.7: Add clear filters button
- [ ] 7.8: Update TaskList query when filters change
- [ ] 7.9: Test filter combinations

### 8. Task Statistics
- [ ] 8.1: Create `src/components/tasks/TaskStats.jsx` component
- [ ] 8.2: Fetch stats using taskService.getStats
- [ ] 8.3: Display counts by status (todo, in_progress, done)
- [ ] 8.4: Display counts by priority (low, medium, high)
- [ ] 8.5: Display overdue count
- [ ] 8.6: Use Material-UI Card or Paper for layout
- [ ] 8.7: Add visual indicators (icons, colors)

### 9. Common Components
- [ ] 9.1: Create `src/components/common/Loading.jsx` with spinner or skeleton
- [ ] 9.2: Create `src/components/common/ErrorMessage.jsx` for error display
- [ ] 9.3: Create `src/components/common/ConfirmDialog.jsx` for delete confirmation
- [ ] 9.4: Style common components consistently
- [ ] 9.5: Make components reusable across the app

### 10. React Query & Routing Setup
- [ ] 10.1: Configure React Query client in `src/App.jsx`
- [ ] 10.2: Set default query options (refetchOnWindowFocus, retry)
- [ ] 10.3: Set up React Router with routes: `/login`, `/register`, `/dashboard`, `/`
- [ ] 10.4: Protect `/dashboard` route with PrivateRoute component
- [ ] 10.5: Redirect `/` to `/dashboard`
- [ ] 10.6: Create 404 Not Found page
- [ ] 10.7: Test navigation flows

### 11. Theme & Styling
- [ ] 11.1: Configure Material-UI theme in `src/App.jsx`
- [ ] 11.2: Set primary and secondary colors
- [ ] 11.3: Configure typography
- [ ] 11.4: Add CssBaseline for consistent styling
- [ ] 11.5: Implement responsive design with breakpoints
- [ ] 11.6: Test dark mode support (optional)
- [ ] 11.7: Ensure consistent spacing and alignment

### 12. Loading & Error States
- [ ] 12.1: Show skeleton screens during data loading
- [ ] 12.2: Show loading spinner for actions (complete, delete, submit)
- [ ] 12.3: Display user-friendly error messages (network errors, 404, 403, 500)
- [ ] 12.4: Implement retry functionality for failed requests
- [ ] 12.5: Show offline banner when network is unavailable
- [ ] 12.6: Test various error scenarios

### 13. Component Testing
- [ ] 13.1: Write tests for Login form: validates inputs, handles errors, submits correctly
- [ ] 13.2: Write tests for TaskCard: displays data correctly, action buttons work
- [ ] 13.3: Write tests for TaskFilters: updates query params, clears filters
- [ ] 13.4: Write tests for TaskForm: validates inputs, creates task, edits task
- [ ] 13.5: Write tests for TaskList: displays tasks, handles loading/error states
- [ ] 13.6: Test component interactions and state updates
- [ ] 13.7: Achieve >70% test coverage

### 14. Integration Testing
- [ ] 14.1: Test login flow end-to-end
- [ ] 14.2: Test registration flow end-to-end
- [ ] 14.3: Test create task and see in list
- [ ] 14.4: Test edit task updates UI correctly
- [ ] 14.5: Test delete task removes from list
- [ ] 14.6: Test filters update displayed tasks
- [ ] 14.7: Test search finds tasks
- [ ] 14.8: Test mark complete updates status

### 15. Responsive Design Validation
- [ ] 15.1: Test on mobile (< 600px): single column, full-width cards, bottom drawer
- [ ] 15.2: Test on tablet (600px - 1200px): two column grid, collapsible sidebar
- [ ] 15.3: Test on desktop (> 1200px): three column grid, persistent sidebar
- [ ] 15.4: Test touch interactions on mobile devices
- [ ] 15.5: Test keyboard navigation on desktop
- [ ] 15.6: Verify smooth transitions and animations

### 16. Documentation & User Guide
- [ ] 16.1: Create `docs/user-guide.md` with feature walkthrough
- [ ] 16.2: Document how to log in, register, create tasks, edit tasks, delete tasks
- [ ] 16.3: Document filtering and search functionality
- [ ] 16.4: Create screenshots or GIFs of key features
- [ ] 16.5: Update README with frontend setup instructions
- [ ] 16.6: Document environment variables (VITE_API_URL)

---

## Files to Create/Modify

| File | Action | Purpose |
|------|--------|---------|
| `src/App.jsx` | Create | React Query provider, theme, routing setup |
| `src/main.jsx` | Create | App entry point |
| `src/services/api.js` | Create | Axios instance with interceptors |
| `src/services/auth.js` | Create | Authentication service layer |
| `src/services/tasks.js` | Create | Task service layer |
| `src/pages/Login.jsx` | Create | Login page component |
| `src/pages/Register.jsx` | Create | Registration page component |
| `src/pages/Dashboard.jsx` | Create | Main dashboard page |
| `src/pages/NotFound.jsx` | Create | 404 page |
| `src/components/auth/PrivateRoute.jsx` | Create | Protected route wrapper |
| `src/components/layout/Layout.jsx` | Create | App layout structure |
| `src/components/layout/AppBar.jsx` | Create | Top navigation bar |
| `src/components/layout/Sidebar.jsx` | Create | Sidebar with filters |
| `src/components/tasks/TaskList.jsx` | Create | Task list with React Query |
| `src/components/tasks/TaskCard.jsx` | Create | Individual task card |
| `src/components/tasks/TaskForm.jsx` | Create | Create/edit task modal |
| `src/components/tasks/TaskFilters.jsx` | Create | Filter panel |
| `src/components/tasks/TaskStats.jsx` | Create | Statistics display |
| `src/components/common/Loading.jsx` | Create | Loading component |
| `src/components/common/ErrorMessage.jsx` | Create | Error display component |
| `src/components/common/ConfirmDialog.jsx` | Create | Confirmation dialog |
| `tests/**/*.test.jsx` | Create | Component and integration tests |
| `docs/user-guide.md` | Create | User documentation |
| `.env.example` | Create | Environment variable template |
| `README.md` | Modify | Add frontend setup instructions |

## Patterns to Follow

| Pattern | Reference | Usage |
|---------|-----------|-------|
| Container/Presenter | React components | Separate logic (hooks) from presentation (JSX) |
| Custom Hooks | `src/hooks/` | Encapsulate reusable logic (useAuth, useTasks) |
| React Query | `@tanstack/react-query` | Server state management, caching, refetching |
| Compound Components | Material-UI patterns | Compose complex components from smaller ones |
| Controlled Forms | react-hook-form | Manage form state declaratively |

## Test Strategy

- [ ] Component tests: render correctly, handle props, user interactions
- [ ] Form tests: validation, submission, error handling
- [ ] Integration tests: full user flows (login -> create task -> edit -> delete)
- [ ] Responsive tests: components render correctly at different breakpoints
- [ ] Accessibility tests: keyboard navigation, ARIA labels, screen reader support
- [ ] Use React Testing Library for user-centric tests
- [ ] Mock API calls with MSW or jest mocks
- [ ] Achieve >70% test coverage

## Validation

- Use `python-task-validator` to verify React component structure and best practices (though it's designed for Python, it can provide general code quality feedback)

## Acceptance Criteria

**ALL must pass:**

- [ ] All tasks completed
- [ ] All gates passing (lint, type-check, tests, build, performance)
- [ ] Users can log in and register
- [ ] Dashboard displays user's tasks
- [ ] Tasks can be created via form
- [ ] Tasks can be edited and deleted
- [ ] Filters update task display correctly
- [ ] Search finds tasks
- [ ] Statistics display accurate counts
- [ ] Responsive on mobile, tablet, desktop
- [ ] Loading states during async operations
- [ ] Error messages are helpful
- [ ] Smooth transitions and animations
- [ ] Keyboard navigation works
- [ ] Frontend successfully calls all API endpoints
- [ ] Authentication tokens work correctly
- [ ] Error responses are handled gracefully
- [ ] Component tests achieve >70% coverage
- [ ] User guide documentation complete
- [ ] Bundle size is reasonable (<500KB gzipped)
- [ ] Frontend loads within 1.5s on 4G

## Rollback Plan

If frontend has critical issues:
1. Revert commits related to Phase 4
2. Remove frontend build from deployment
3. Keep backend (Phases 1-3) running
4. Identify specific broken component or feature
5. Fix in development environment
6. Test thoroughly before redeploying

For production (if already deployed):
1. Revert to previous working frontend build
2. Keep backend online (independent from frontend)
3. Display maintenance banner to users
4. Fix issues in staging environment
5. Run full test suite before production deployment
6. Deploy new build with monitoring
7. Notify users of any downtime

---

## Implementation Notes

### Environment Variables
```
VITE_API_URL=http://localhost:3000/api
```

### React Query Configuration
```javascript
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
      retry: 1,
      staleTime: 60000  // 1 minute
    }
  }
});
```

### Material-UI Breakpoints
- xs (mobile): < 600px
- sm (tablet): 600px - 900px
- md (tablet/small desktop): 900px - 1200px
- lg (desktop): 1200px - 1536px
- xl (large desktop): > 1536px

### API Error Handling
```javascript
// In Axios response interceptor
if (error.response?.status === 401) {
  localStorage.removeItem('authToken');
  window.location.href = '/login';
}
```

### Task Card Priority Colors
```javascript
const priorityColors = {
  low: 'success',    // green
  medium: 'warning', // orange
  high: 'error'      // red
};
```

### Performance Optimization
- Use React.memo for expensive components
- Lazy load routes with React.lazy and Suspense
- Code split by route
- Optimize images (use WebP, lazy loading)
- Tree shake unused Material-UI components
- Monitor bundle size with Vite build analyzer
- Use production build for deployment

### Accessibility Considerations
- Add ARIA labels to buttons and inputs
- Ensure sufficient color contrast
- Support keyboard navigation (Tab, Enter, Escape)
- Provide focus indicators
- Use semantic HTML (button, nav, main, etc.)
- Test with screen reader