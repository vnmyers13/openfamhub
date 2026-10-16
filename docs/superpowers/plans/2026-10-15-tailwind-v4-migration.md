# Tailwind CSS v4 Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move the Vite frontend from Tailwind CSS 3 to Tailwind CSS 4 while preserving its visual design and removing the Tailwind 3 build-time dependency advisories.

**Architecture:** Use Tailwind v4's first-party Vite plugin instead of PostCSS. Move the small JavaScript theme into CSS with `@theme` and explicitly preserve class-based dark mode with a custom variant.

**Tech Stack:** React 19, Vite 8, Tailwind CSS 4, `@tailwindcss/vite`, Vitest 5, ESLint 10.

**Spec:** User request in this session: complete the first unchecked TODO item, Tailwind CSS 3 → 4 migration.

## Global Constraints

- Require Node `^22.22.2 || >=24.15.0` for frontend tooling.
- Preserve `primary`, `primary-dark`, and `font-display` utility class behavior.
- Preserve class-based dark mode and all frontend coverage thresholds.
- Remove Tailwind 3, its PostCSS configuration, and no-longer-needed Autoprefixer.

## Review Focus

- Dark-mode utilities must respond to the app's `.dark` class.
- Existing primary-color and display-font utilities must compile unchanged.
- Calendar CSS must remain before Tailwind's generated CSS.
- OCR/PWA production-build output must remain intact.
- The lockfile must no longer resolve Tailwind 3's advisory dependency tree.

---

### Task 1: Migrate Tailwind build integration and theme

**Files:**
- Modify: `frontend/package.json`, `frontend/package-lock.json`, `frontend/vite.config.ts`, `frontend/src/index.css`
- Delete: `frontend/tailwind.config.js`, `frontend/postcss.config.js`

**Interfaces:**
- Consumes: Vite's plugin array and the frontend CSS entry point.
- Produces: Tailwind v4 utility generation through `@tailwindcss/vite` and CSS variables matching the old utilities.

- [ ] **Step 1: Establish the pre-migration build baseline**

Run: `npx --yes -p node@22 node node_modules/vite/bin/vite.js build`

Expected: PASS using Tailwind 3.

- [ ] **Step 2: Install v4 dependencies**

Run the Tailwind v4 upgrade tool under Node 22; keep `tailwindcss@4` and `@tailwindcss/vite@4` as the required dev dependencies and remove Tailwind 3 and Autoprefixer.

- [ ] **Step 3: Configure Vite**

In `frontend/vite.config.ts`, import `@tailwindcss/vite` as `tailwindcss` and add `tailwindcss()` next to the React and PWA plugins.

- [ ] **Step 4: Move the theme to CSS**

In `frontend/src/index.css`, retain the calendar CSS import first, replace v3 directives with `@import "tailwindcss"`, define `--color-primary`, `--color-primary-dark`, and `--font-display` in `@theme`, and define `dark` as `&:where(.dark, .dark *)`.

- [ ] **Step 5: Remove obsolete configuration files**

Delete the v3 Tailwind and PostCSS configuration files.

- [ ] **Step 6: Verify the production build**

Run OCR asset preparation, TypeScript build, and Vite build under Node 22.

Expected: PASS with PWA output and all page chunks.

- [ ] **Step 7: Commit**

Commit the migration files with message `Migrate frontend to Tailwind CSS 4`.

### Task 2: Verify and close the roadmap item

**Files:**
- Modify: `TODO.md`

**Interfaces:**
- Consumes: the Tailwind v4 integration from Task 1.
- Produces: verified frontend checks and an accurate roadmap entry.

- [ ] **Step 1: Run frontend test coverage**

Run: `npx --yes -p node@22 node node_modules/vitest/vitest.mjs run --coverage`

Expected: PASS with configured thresholds met.

- [ ] **Step 2: Run lint and inspect dependencies**

Run ESLint under Node 22 and `npm ls tailwindcss @tailwindcss/vite`.

Expected: no lint errors; Tailwind CSS 4 and its Vite plugin resolve with no Tailwind 3 package.

- [ ] **Step 3: Tick the Tailwind advisory TODO item and commit**

Record the v4 remediation in `TODO.md` and commit it with the migration if it remains one logical change.

## Self-Review

- Task 1 covers dependency, Vite, CSS-theme, dark-mode, and obsolete-config changes.
- Task 2 covers production build, test coverage, lint, dependency verification, and roadmap status.
- The build and coverage checks exercise all Review Focus conditions except visual appearance, which retains the same utility names and color values.
