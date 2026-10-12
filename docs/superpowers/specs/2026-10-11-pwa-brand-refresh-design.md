# PWA Brand Refresh — Design

Date: 2026-10-11
Status: Approved (icon concept B, "brand pop" palette)

## Context

The installable PWA has a plain flat-indigo house favicon, three bare PNGs
(180/192/512) with no maskable variant, a white splash that flashes against the
dark-themed app, and no iOS favicon metadata. This design refreshes the visual
identity and install experience around a new "house + calendar" mark.

User decisions taken during brainstorming:

- **Icon concept:** house + calendar hybrid (B) — indigo gradient tile, white
  glyph, coral heart as the date marker.
- **Palette:** `theme_color #4F46E5` (brand pop), `background_color #1E1B4B`
  (dark splash, no more white launch flash).
- **Scope:** dark splash + title bar, maskable variant, iOS + favicon
  consistency, and a thin-line mono favicon for browser tabs.

## Goals / non-goals

**In scope:** new icon artwork, PWA manifest colors/description/icons, iOS meta
and touch icon in `index.html`, a reproducible icon-generation script.

**Out of scope:** backend changes, wall-display branding, app theme changes, the
white-flash fix inside the running app itself (only the PWA chrome/splash), and
changing the product name (`OpenFamHub` stays).

## 1. Icon artwork

Three source SVGs live in `frontend/public/icons/` and double as the design
source:

| File | Description |
|---|---|
| `icon-app.svg` | Rounded gradient tile (512, rx 115) + white house/calendar glyph + coral heart. Basis for the app PNGs. |
| `icon-maskable.svg` | Same gradient **full-bleed** (no rounded corners), glyph scaled into the 80% safe zone (content inside a ~410px circle on 512) so Android's mask doesn't clip it. |
| `icon-mono.svg` | The mark as a thin indigo outline (house + calendar grid + heart) on a transparent canvas. Favicon source. |

Generated and committed PNGs (same directory):

| File | Size | Purpose |
|---|---|---|
| `icon-192.png` | 192×192 | Android install, `any` |
| `icon-512.png` | 512×512 | Store / large Android, `any` |
| `maskable-icon-512.png` | 512×512 | `maskable` |
| `apple-touch-icon-180x180.png` | 180×180 | iOS home-screen icon (full-bleed square) |

`frontend/public/favicon.svg` is replaced with the mono glyph so the tab/bookmark
icon stays legible at 16px instead of showing a tiny rounded tile.

## 2. PWA manifest (`frontend/vite.config.ts`)

- `theme_color: "#4F46E5"`, `background_color: "#1E1B4B"`.
- Add `description: "OpenFamHub — family calendar for home"`.
- `icons` becomes:
  - `/icons/icon-192.png` (no purpose),
  - `/icons/icon-512.png` (no purpose),
  - `/icons/maskable-icon-512.png` (`purpose: "maskable"`),
  - `/icons/apple-touch-icon-180x180.png` (no manifest purpose — iOS consumes it via the `apple-touch-icon` link).
- `includeAssets: "icons/*.png"` already covers all of the above.

## 3. `frontend/index.html`

- `<meta name="theme-color" content="#4F46E5">`
- `<meta name="apple-mobile-web-app-capable" content="yes">`
- `<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">`
- `<link rel="apple-touch-icon" href="/icons/apple-touch-icon-180x180.png">`
- Keep the existing `<link rel="icon" href="/favicon.svg">` (now the mono glyph).

## 4. Regeneration tooling

- Add devDependency `@resvg/resvg-js` (cross-platform SVG→PNG rasterizer).
- `frontend/scripts/generate-icons.mjs` reads the three source SVGs and writes the
  four PNGs at the exact sizes above.
- `npm run icons` in `frontend/package.json`.
- PNGs are **committed**; the pipeline has no new build step. The script exists so
  future tweaks to the art are one command.

## 5. Verification

- `npm run build`; confirm `dist/manifest.webmanifest` has the new colors +
  description + the four icons.
- Confirm `dist/` contains the new PNGs and `favicon.svg`, and that the precached
  SW bundle references the new files (installed PWAs pick up the new icons on
  their next update since the build hash changes).
- Dev-server check of `index.html` meta tags.

## Files touched

- `frontend/public/icons/icon-app.svg` (new)
- `frontend/public/icons/icon-maskable.svg` (new)
- `frontend/public/icons/icon-mono.svg` (new)
- `frontend/public/icons/icon-192.png`, `icon-512.png` (regenerated)
- `frontend/public/icons/maskable-icon-512.png`, `apple-touch-icon-180x180.png` (new)
- `frontend/public/favicon.svg` (replaced)
- `frontend/vite.config.ts` (manifest)
- `frontend/index.html` (meta + touch-icon link)
- `frontend/package.json` / `package-lock.json` (`@resvg/resvg-js`, `icons` script)
- `frontend/scripts/generate-icons.mjs` (new)
- `README.md` (note the `npm run icons` regeneration step)