# PWA Brand Refresh Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the flat-house PWA visuals with the approved "house + calendar" gradient mark, maskable/iOS icon variants, and a dark splash/title-bar palette.

**Architecture:** Three source SVGs (app tile, maskable tile, mono favicon glyph) live in `frontend/public/icons/` and are rasterized to committed PNGs by a small Node script (`npm run icons`). The PWA manifest and `index.html` point at the new files and dark colors; the build is unchanged (PNGs ship in the repo). Spec: `docs/superpowers/specs/2026-10-11-pwa-brand-refresh-design.md`.

**Tech Stack:** SVG, `@resvg/resvg-js` (dev-time rasterizer), Vite + `vite-plugin-pwa` 1.3, React 19. No backend changes.

## Global Constraints

- Palette (verbatim from spec): tile gradient `#6366F1` → `#4F46E5` → `#4338CA`; heart accent `#FDA4AF`; glyph white `#ffffff`; `theme_color` `#4F46E5`; `background_color` `#1E1B4B`; favicon line color `#4F46E5`.
- Icon PNG set (exact names under `frontend/public/icons/`): `icon-192.png` (192), `icon-512.png` (512), `maskable-icon-512.png` (512), `apple-touch-icon-180x180.png` (180). `favicon.svg` = mono glyph.
- App/tile SVGs are 512×512 `viewBox`. Maskable art is full-bleed (no rounded corners) with the glyph scaled to 0.9 about the center.
- Product name stays "OpenFamHub"; `short_name` stays "OpenFamHub".
- PNGs are committed and committed only once — do not let any build step regenerate them.
- Frontend verification commands run from `frontend/`: `npm run lint` and `npm run build` (build = `tsc -b && vite build`).
- **Execution setup:** create an isolated worktree on a new branch via superpowers:using-git-worktrees at execution time (e.g. `.worktrees/pwa-brand-refresh` on `feat/pwa-brand`). All tasks below run inside it; the branch merges back to `feat/0.30-security` after review.

---

### Task 1: Icon source SVGs + favicon

**Files:**
- Create: `frontend/public/icons/icon-app.svg`
- Create: `frontend/public/icons/icon-maskable.svg`
- Create: `frontend/public/icons/icon-mono.svg`
- Modify: `frontend/public/favicon.svg` (replace content with the mono glyph)

**Interfaces:**
- Produces: `icon-app.svg`, `icon-maskable.svg`, `icon-mono.svg`, `favicon.svg` — read by `generate-icons.mjs` in Task 2. `icon-maskable.svg` is the source for both `maskable-icon-512.png` and `apple-touch-icon-180x180.png`.

- [ ] **Step 1: Create `frontend/public/icons/icon-app.svg`**

```svg
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512">
  <defs>
    <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0" stop-color="#6366F1"/>
      <stop offset=".55" stop-color="#4F46E5"/>
      <stop offset="1" stop-color="#4338CA"/>
    </linearGradient>
    <radialGradient id="sheen" cx=".5" cy=".28" r=".9">
      <stop offset="0" stop-color="#ffffff" stop-opacity=".28"/>
      <stop offset="1" stop-color="#ffffff" stop-opacity="0"/>
    </radialGradient>
  </defs>
  <rect width="512" height="512" rx="115" fill="url(#bg)"/>
  <rect width="512" height="512" rx="115" fill="url(#sheen)"/>
  <rect x="140" y="252" width="232" height="168" rx="18" fill="#ffffff"/>
  <path d="M256 118 L120 252 H392 L256 118 Z" fill="#ffffff"/>
  <rect x="146" y="258" width="220" height="30" rx="10" fill="url(#bg)"/>
  <circle cx="170" cy="273" r="5" fill="url(#bg)"/>
  <circle cx="342" cy="273" r="5" fill="url(#bg)"/>
  <path d="M206 304 V412 M306 304 V412" stroke="url(#bg)" stroke-width="8" stroke-linecap="round"/>
  <path d="M154 316 H358 M154 344 H358" stroke="url(#bg)" stroke-width="8" stroke-linecap="round"/>
  <path d="M256 370c-3-3-7-5-11-5-8 0-14 6-14 13 0 8 13 18 25 26 12-8 25-18 25-26 0-7-6-13-14-13-4 0-8 2-11 5z" fill="#FDA4AF"/>
</svg>
```

- [ ] **Step 2: Create `frontend/public/icons/icon-maskable.svg`**

Same art, but: both background rects are full-bleed (drop `rx="115"`), and the glyph group is wrapped in `<g transform="translate(256 256) scale(.9) translate(-256 -256)">`:

```svg
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512">
  <defs>
    <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0" stop-color="#6366F1"/>
      <stop offset=".55" stop-color="#4F46E5"/>
      <stop offset="1" stop-color="#4338CA"/>
    </linearGradient>
    <radialGradient id="sheen" cx=".5" cy=".28" r=".9">
      <stop offset="0" stop-color="#ffffff" stop-opacity=".28"/>
      <stop offset="1" stop-color="#ffffff" stop-opacity="0"/>
    </radialGradient>
  </defs>
  <rect width="512" height="512" fill="url(#bg)"/>
  <rect width="512" height="512" fill="url(#sheen)"/>
  <g transform="translate(256 256) scale(.9) translate(-256 -256)">
    <rect x="140" y="252" width="232" height="168" rx="18" fill="#ffffff"/>
    <path d="M256 118 L120 252 H392 L256 118 Z" fill="#ffffff"/>
    <rect x="146" y="258" width="220" height="30" rx="10" fill="url(#bg)"/>
    <circle cx="170" cy="273" r="5" fill="url(#bg)"/>
    <circle cx="342" cy="273" r="5" fill="url(#bg)"/>
    <path d="M206 304 V412 M306 304 V412" stroke="url(#bg)" stroke-width="8" stroke-linecap="round"/>
    <path d="M154 316 H358 M154 344 H358" stroke="url(#bg)" stroke-width="8" stroke-linecap="round"/>
    <path d="M256 370c-3-3-7-5-11-5-8 0-14 6-14 13 0 8 13 18 25 26 12-8 25-18 25-26 0-7-6-13-14-13-4 0-8 2-11 5z" fill="#FDA4AF"/>
  </g>
</svg>
```

- [ ] **Step 3: Create `frontend/public/icons/icon-mono.svg` and replace `frontend/public/favicon.svg`**

Both have identical content (the thin indigo outline glyph):

```svg
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512">
  <path d="M256 132 L136 256 H376 L256 132 Z" fill="none" stroke="#4F46E5" stroke-width="16" stroke-linejoin="round"/>
  <rect x="152" y="256" width="208" height="150" rx="14" fill="none" stroke="#4F46E5" stroke-width="16"/>
  <path d="M164 286 H348" stroke="#4F46E5" stroke-width="16" stroke-linecap="round"/>
  <circle cx="176" cy="271" r="6" fill="#4F46E5"/>
  <circle cx="336" cy="271" r="6" fill="#4F46E5"/>
  <path d="M210 300 V406 M302 300 V406" stroke="#4F46E5" stroke-width="12" stroke-linecap="round"/>
  <path d="M158 330 H354 M158 360 H354" stroke="#4F46E5" stroke-width="12" stroke-linecap="round"/>
  <path d="M256 372c-3-3-7-5-11-5-8 0-14 6-14 13 0 8 13 18 25 26 12-8 25-18 25-26 0-7-6-13-14-13-4 0-8 2-11 5z" fill="none" stroke="#4F46E5" stroke-width="12"/>
</svg>
```

(`favicon.svg` becomes exactly the same bytes as `icon-mono.svg`.)

- [ ] **Step 4: Verify all four files are well-formed XML**

Run (repo root):
```bash
python3 -c "import sys, xml.dom.minidom as m; [m.parse(p) for p in sys.argv[1:]]; print('well-formed')" frontend/public/icons/icon-app.svg frontend/public/icons/icon-maskable.svg frontend/public/icons/icon-mono.svg frontend/public/favicon.svg
```
Expected: `well-formed`.

- [ ] **Step 5: Commit**

```bash
git add frontend/public/icons/icon-app.svg frontend/public/icons/icon-maskable.svg frontend/public/icons/icon-mono.svg frontend/public/favicon.svg
git commit -m "feat(pwa): add icon source SVGs"
```

---

### Task 2: Icon generator + PNGs

**Files:**
- Create: `frontend/scripts/generate-icons.mjs`
- Modify: `frontend/package.json` (add `icons` script and devDependency `@resvg/resvg-js`)
- Modify: `frontend/package-lock.json` (via `npm install`)
- Produced: `frontend/public/icons/icon-192.png`, `icon-512.png`, `maskable-icon-512.png`, `apple-touch-icon-180x180.png`

**Interfaces:**
- Consumes: the three SVGs from Task 1.
- Produces: the four committed PNGs consumed by the manifest in Task 3.

- [ ] **Step 1: Install the rasterizer**

Run (in `frontend/`):
```bash
npm install --save-dev @resvg/resvg-js
```
Expected: added to `package.json` `devDependencies` and `package-lock.json`.

- [ ] **Step 2: Create `frontend/scripts/generate-icons.mjs`**

```js
import { Resvg } from '@resvg/resvg-js'
import { readFileSync, writeFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const here = dirname(fileURLToPath(import.meta.url))
const iconsDir = resolve(here, '..', 'public', 'icons')
const svg = (name) => readFileSync(resolve(iconsDir, name), 'utf8')
const render = (src, size) => new Resvg(src, { fitTo: { mode: 'width', value: size } }).render().asPng()

const jobs = [
  ['icon-app.svg', 192, 'icon-192.png'],
  ['icon-app.svg', 512, 'icon-512.png'],
  ['icon-maskable.svg', 512, 'maskable-icon-512.png'],
  ['icon-maskable.svg', 180, 'apple-touch-icon-180x180.png'],
]

for (const [src, size, out] of jobs) {
  const png = render(svg(src), size)
  writeFileSync(resolve(iconsDir, out), png)
  console.log(`${out}: ${png.length} bytes`)
}
```

- [ ] **Step 3: Add the npm script in `frontend/package.json`**

Change the `"scripts"` block to:

```json
  "scripts": {
    "dev": "vite",
    "build": "tsc -b && vite build",
    "lint": "eslint .",
    "preview": "vite preview",
    "icons": "node scripts/generate-icons.mjs"
  },
```

- [ ] **Step 4: Run the generator**

Run (in `frontend/`):
```bash
npm run icons
```
Expected: four `wrote …` lines with non-zero byte counts, and no resvg errors.

- [ ] **Step 5: Verify the PNGs**

```bash
file frontend/public/icons/icon-192.png frontend/public/icons/icon-512.png frontend/public/icons/maskable-icon-512.png frontend/public/icons/apple-touch-icon-180x180.png
sips -g pixelWidth -g pixelHeight frontend/public/icons/icon-192.png frontend/public/icons/icon-512.png frontend/public/icons/maskable-icon-512.png frontend/public/icons/apple-touch-icon-180x180.png
```
Expected: four PNG images; pixel dimensions 192×192, 512×512, 512×512, 180×180 respectively. `icon-192.png`/`icon-512.png` have rounded corners (top-left corner pixel = transparent); `maskable-icon-512.png`/`apple-touch-icon-180x180.png` are fully opaque.

You can check the corner pixel of `icon-512.png` quickly with:
```bash
python3 -c "
import struct
png = open('frontend/public/icons/icon-512.png','rb').read()
print('PNG header ok' if png[:8] == b'\x89PNG\r\n\x1a\n' else 'BAD')
"
```

- [ ] **Step 6: Commit**

```bash
git add frontend/scripts/generate-icons.mjs frontend/package.json frontend/package-lock.json frontend/public/icons/icon-192.png frontend/public/icons/icon-512.png frontend/public/icons/maskable-icon-512.png frontend/public/icons/apple-touch-icon-180x180.png
git commit -m "feat(pwa): generate PWA icon PNGs"
```

---

### Task 3: Manifest + index.html wire-up

**Files:**
- Modify: `frontend/vite.config.ts` (the `VitePWA({ ... manifest: { ... } })` block, lines 12–48)
- Modify: `frontend/index.html` (`<head>`, lines 4–6)

**Interfaces:**
- Consumes: the four PNGs from Task 2.
- Produces: `dist/manifest.webmanifest` with the new colors/description/icons and a `dist/index.html` with the new meta tags and touch-icon link. Verified by build output here and during final Task 4.

- [ ] **Step 1: Update the manifest in `frontend/vite.config.ts`**

Replace the `manifest` object (currently `name` through `icons`) with:

```ts
      manifest: {
        name: 'OpenFamHub',
        short_name: 'OpenFamHub',
        description: 'OpenFamHub — family calendar for home',
        theme_color: '#4F46E5',
        background_color: '#1E1B4B',
        display: 'standalone',
        start_url: '/',
        icons: [
          { src: '/icons/icon-192.png', sizes: '192x192', type: 'image/png' },
          { src: '/icons/icon-512.png', sizes: '512x512', type: 'image/png' },
          { src: '/icons/maskable-icon-512.png', sizes: '512x512', type: 'image/png', purpose: 'maskable' },
          { src: '/icons/apple-touch-icon-180x180.png', sizes: '180x180', type: 'image/png', purpose: 'apple-touch-icon' },
        ],
      },
```

Leave `registerType: 'autoUpdate'` and `includeAssets: 'icons/*.png'` unchanged.

- [ ] **Step 2: Update `frontend/index.html`**

Replace lines 4–6:

```html
    <link rel="icon" type="image/svg+xml" href="/favicon.svg" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>OpenFamHub</title>
```

with:

```html
    <meta name="theme-color" content="#4F46E5" />
    <meta name="apple-mobile-web-app-capable" content="yes" />
    <meta name="apple-mobile-web-app-status-bar-style" content="black-translucent" />
    <link rel="icon" type="image/svg+xml" href="/favicon.svg" />
    <link rel="apple-touch-icon" href="/icons/apple-touch-icon-180x180.png" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>OpenFamHub</title>
```

- [ ] **Step 3: Build and verify**

Run (in `frontend/`):
```bash
npm run build
```
Expected: exit 0 (any pre-existing chunk-size warning is fine).

Then:
```bash
grep -o '"theme_color":"[^"]*"' dist/manifest.webmanifest
grep -o '"background_color":"[^"]*"' dist/manifest.webmanifest
grep -o '"description":"[^"]*"' dist/manifest.webmanifest
grep -o '"maskable"' dist/manifest.webmanifest
grep -o '"apple-touch-icon"' dist/manifest.webmanifest
grep -o 'theme-color[^>]*' dist/index.html
grep -o 'apple-touch-icon[^>]*' dist/index.html
ls dist/icons/
```
Expected:
- `"theme_color":"#4F46E5"`, `"background_color":"#1E1B4B"`, `"description":"OpenFamHub — family calendar for home"`
- `maskable` and `apple-touch-icon` purposes present
- `dist/index.html` has `name="theme-color" content="#4F46E5"` and the `apple-touch-icon` link
- `dist/icons/` contains the four PNGs plus `favicon.svg` (copied via `includeAssets` behavior — verify `icon-512.png` and `maskable-icon-512.png` at minimum).

- [ ] **Step 4: Commit**

```bash
git add frontend/vite.config.ts frontend/index.html
git commit -m "feat(pwa): refresh manifest and iOS metadata"
```

---

### Task 4: README note + full verification

**Files:**
- Modify: `README.md` (short note after the Stack table, line 81/82)
- Untracked (do not commit): any build artifacts in `frontend/dist/`

**Interfaces:**
- Consumes: everything from Tasks 1–3.
- Produces: an all-green final check for the branch.

- [ ] **Step 1: Add the regeneration note to `README.md`**

Insert between the Stack table (ends line 81) and `## License` (line 83):

```markdown
PWA icons (`favicon.svg`, 180/192/512, maskable) are generated from the source SVGs in `frontend/public/icons/` with `npm run icons` (from `frontend/`).
```

- [ ] **Step 2: Full frontend verification**

Run (in `frontend/`):
```bash
npm run lint
npm run build
```
Expected: lint exits 0 with no errors; build exits 0. Re-confirm the greps from Task 3 Step 3 still hold after the clean rebuild.

- [ ] **Step 3: Backend sanity (unchanged)**

Run (from `backend/`, in the activated venv):
```bash
SECRET_KEY=ci-only-not-a-real-secret-0123456789abcdef python -m pytest -q
```
Expected: all green (`32 passed` baseline — a previously-added PWA change must not affect this). Only run this if the backend venv exists; the PWA pass otherwise touches nothing backend-side.

- [ ] **Step 4: Commit**

```bash
git add README.md
git commit -m "docs: note PWA icon regeneration"
```

- [ ] **Step 5: Merge back**

- Commit any remaining work, then switch to `feat/0.30-security` and merge the worktree branch (fast-forward) per the repo's established pattern (see the infra-hardening pass: `5470b3b..fcec685`).
- Push both remotes: `git push forgejo feat/0.30-security` and `git push origin feat/0.30-security`.
- Leave the parked auth-gate regression test (`backend/tests/test_phase2.py`, a modified-but-uncommitted RED test in the main workspace) untouched; it belongs to the separate admin self-update task. Worktree checkouts don't carry uncommitted changes, so it stays where it is.