# Hello World Phase 1: Page Implementation

**Status:** Pending
**Master Plan:** [MASTER_PLAN.md](MASTER_PLAN.md)
**Depends On:** N/A

---

## Process Wrapper (MANDATORY)
- [ ] Read previous notes: `notes/NOTES_hello_world_phase_0.md` (N/A - initial phase)
- [ ] doc-sync-manager agent: sync tasks to ACTIVE.md (REQUIRED)
- [ ] **[IMPLEMENTATION - see Tasks below]**
- [ ] Pre-validation (ALL required):
  ```bash
  cd frontend
  # Code quality
  pnpm lint --fix
  pnpm exec tsc --noEmit
  pnpm build
  pnpm audit

  # Architecture checks
  node scripts/check-api-usage.js        # Must use @/lib/api.ts
  node scripts/check-hardcoded-urls.js   # No localhost/IP URLs (CORS)
  ```
- [ ] i18n-translator-expert agent: verify FR/EN keys (REQUIRED)
- [ ] task-validator agent: full validation (REQUIRED)
- [ ] Fix loop: repeat pre-validation until clean
- [ ] doc-sync-manager agent: cleanup ACTIVE.md, BUGS.md, update plan status (REQUIRED)
- [ ] Write `notes/NOTES_hello_world_phase_1.md` (REQUIRED)

## Gates (must pass before completion)

**ALL gates are BLOCKING.**

- tsc: `command: cd frontend && pnpm exec tsc --noEmit` - 0 errors
- eslint: `command: cd frontend && pnpm lint` - 0 errors
- build: `command: cd frontend && pnpm build` - success
- audit: `command: cd frontend && pnpm audit` - 0 high/critical vulnerabilities
- i18n: all strings translated (FR + EN)
- architecture: `command: cd frontend && node scripts/check-api-usage.js && node scripts/check-hardcoded-urls.js` - 0 violations

---

## Overview

This phase implements a complete Hello World page in Next.js 14 with App Router. The page displays a greeting message with the current date/time, fully styled with Tailwind CSS. All user-facing strings are internationalized for French and English using next-intl. The implementation follows project conventions including centralized API patterns and Zustand for state management.

## Dependencies
- Previous phase: N/A (initial phase)
- Backend endpoints: None required (client-side date/time only)
- External: next-intl configured, Tailwind CSS configured

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Hydration mismatch with dynamic date | Medium | Medium | Use useEffect hook to update date client-side only |
| Missing i18n keys causing runtime errors | Low | Medium | Validate all keys exist before marking phase complete |
| Responsive design issues on edge cases | Low | Low | Test on multiple breakpoints during implementation |

---

## Tasks

### 1. Create HelloGreeting Component
- [ ] 1.1: Create `HelloGreeting.tsx` component in `frontend/src/components/`
- [ ] 1.2: Implement greeting message display using next-intl `useTranslations` hook
- [ ] 1.3: Add date/time display with locale-aware formatting using `useFormatter` from next-intl
- [ ] 1.4: Implement client-side date update using `useEffect` to avoid hydration mismatch
- [ ] 1.5: Add Tailwind CSS styling for typography, spacing, and layout
- [ ] 1.6: Make component responsive (mobile, tablet, desktop)

### 2. Create Hello Page Route
- [ ] 2.1: Create page route at `frontend/src/app/[locale]/hello/page.tsx`
- [ ] 2.2: Set up page metadata (title, description) with i18n support
- [ ] 2.3: Import and render `HelloGreeting` component
- [ ] 2.4: Add appropriate semantic HTML structure (main, section, h1)
- [ ] 2.5: Ensure page works with both `/en/hello` and `/fr/hello` routes

### 3. Add Internationalization Keys
- [ ] 3.1: Add English translations to `frontend/src/i18n/locales/en.json`
- [ ] 3.2: Add French translations to `frontend/src/i18n/locales/fr.json`
- [ ] 3.3: Include keys for: greeting title, greeting message, date/time labels, page metadata
- [ ] 3.4: Verify all keys are properly namespaced (e.g., `hello.greeting`, `hello.dateLabel`)

### 4. Styling and Responsiveness
- [ ] 4.1: Apply Tailwind utility classes for consistent design
- [ ] 4.2: Center content vertically and horizontally on page
- [ ] 4.3: Add appropriate font sizes (responsive: text-2xl md:text-4xl lg:text-5xl)
- [ ] 4.4: Add subtle visual styling (shadow, rounded corners, background)
- [ ] 4.5: Ensure proper contrast ratios for accessibility (WCAG AA)

### 5. Testing
- [ ] 5.1: Write unit tests for `HelloGreeting` component
- [ ] 5.2: Test component renders greeting message correctly
- [ ] 5.3: Test date/time formatting for both EN and FR locales
- [ ] 5.4: Test responsive behavior at different breakpoints
- [ ] 5.5: Verify no console errors or warnings

---

## Files to Create/Modify

| File | Action | Purpose |
|------|--------|---------|
| `frontend/src/components/HelloGreeting.tsx` | Create | Main greeting component with date/time display |
| `frontend/src/app/[locale]/hello/page.tsx` | Create | Hello World page route |
| `frontend/src/i18n/locales/en.json` | Modify | Add English translations for hello namespace |
| `frontend/src/i18n/locales/fr.json` | Modify | Add French translations for hello namespace |
| `frontend/src/__tests__/components/HelloGreeting.test.tsx` | Create | Unit tests for greeting component |

## Components to Create

| Component | Location | Props | Purpose |
|-----------|----------|-------|---------|
| `HelloGreeting` | `components/` | `className?: string` | Display greeting message with current date/time |

## i18n Keys to Add

| Key | FR | EN |
|-----|----|----|
| `hello.title` | Bonjour le Monde | Hello World |
| `hello.greeting` | Bienvenue sur notre application ! | Welcome to our application! |
| `hello.currentDateTime` | Date et heure actuelles | Current date and time |
| `hello.pageTitle` | Page Bonjour | Hello Page |
| `hello.pageDescription` | Une simple page de bienvenue avec la date et l'heure | A simple greeting page with date and time |

## Patterns to Follow

| Pattern | Reference | Usage |
|---------|-----------|-------|
| API calls | `lib/api.ts` | Centralized, never in components (N/A for this phase) |
| State | `store/` | Zustand for global state (N/A for this simple page) |
| Types | `types/index.ts` | All interfaces here |
| Components | `components/Button.tsx` | Small, single responsibility |
| i18n | next-intl docs | Use `useTranslations` hook, namespace keys |
| Date formatting | next-intl `useFormatter` | Locale-aware date/time formatting |

## Accessibility Checklist
- [ ] Semantic HTML elements used (main, section, h1, time)
- [ ] ARIA labels where needed (time element with datetime attribute)
- [ ] Keyboard navigation works (N/A - no interactive elements)
- [ ] Color contrast sufficient (WCAG AA minimum)
- [ ] Focus states visible (N/A - no focusable elements)

## Acceptance Criteria

**ALL must pass:**

- [ ] All tasks completed
- [ ] All gates passing (tsc, eslint, build, audit, architecture checks)
- [ ] All i18n keys added (FR + EN)
- [ ] Page renders at `/en/hello` and `/fr/hello`
- [ ] Greeting message displays correctly in both languages
- [ ] Date/time displays with proper locale formatting
- [ ] Responsive design works (mobile, tablet, desktop)
- [ ] Accessibility requirements met (semantic HTML, contrast)
- [ ] No hydration mismatches or console errors
- [ ] Unit tests pass

## Rollback Plan

To safely revert Phase 1 changes:

1. Remove created files:
   ```bash
   rm frontend/src/components/HelloGreeting.tsx
   rm frontend/src/app/[locale]/hello/page.tsx
   rm frontend/src/__tests__/components/HelloGreeting.test.tsx
   ```
2. Revert i18n changes:
   ```bash
   git checkout -- frontend/src/i18n/locales/en.json
   git checkout -- frontend/src/i18n/locales/fr.json
   ```
3. Verify no traces: `git status` (should show clean state)

---

## Agents to Use

| When | Agent | Purpose |
|------|-------|---------|
| After implementation | `code-review-expert` | Code quality review |
| After implementation | `i18n-translator-expert` | REQUIRED - translation check |
| After implementation | `task-validator` | REQUIRED - validation |
| Start + End | `doc-sync-manager` | REQUIRED - documentation |
| For UI components | `ux-ui-design-expert` | Design review |

## Implementation Notes

**Hydration Strategy:**
To avoid hydration mismatches with the dynamic date/time, the component should:
1. Render a placeholder or skeleton on initial server render
2. Use `useEffect` to update the date/time client-side after mount
3. Optionally use `useState` to store the current time and update it periodically

**Example pattern:**
```tsx
'use client';

import { useState, useEffect } from 'react';
import { useTranslations, useFormatter } from 'next-intl';

export function HelloGreeting() {
  const t = useTranslations('hello');
  const format = useFormatter();
  const [currentTime, setCurrentTime] = useState<Date | null>(null);

  useEffect(() => {
    setCurrentTime(new Date());
    const interval = setInterval(() => setCurrentTime(new Date()), 1000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="...">
      <h1>{t('title')}</h1>
      <p>{t('greeting')}</p>
      {currentTime && (
        <time dateTime={currentTime.toISOString()}>
          {format.dateTime(currentTime, {
            dateStyle: 'full',
            timeStyle: 'medium'
          })}
        </time>
      )}
    </div>
  );
}
```

**Tailwind Classes Reference:**
- Container: `min-h-screen flex items-center justify-center bg-gradient-to-br from-blue-50 to-indigo-100`
- Card: `bg-white rounded-2xl shadow-xl p-8 md:p-12 max-w-lg mx-4`
- Title: `text-3xl md:text-4xl lg:text-5xl font-bold text-gray-900 mb-4`
- Message: `text-lg md:text-xl text-gray-600 mb-6`
- Time: `text-sm md:text-base text-indigo-600 font-medium`
