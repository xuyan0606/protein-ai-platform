# Protein AI Platform Frontend

React + TypeScript + Vite frontend for the Protein AI Platform. The app covers
authenticated chat, project workspaces, PDB analysis, Wiki embedding, report
publishing, and structured result visualization for protein tools.

## Development

Use port `4200` for local frontend development. The integrated Docker stack
serves the production frontend through Nginx on the same host port.

```bash
npm install
npm run dev -- --host 0.0.0.0 --port 4200
```

Production build:

```bash
npm run build
```

Preview a production build locally:

```bash
npm run preview
```

## App Structure

- `src/pages/` contains route-level screens such as chat, login, Wiki, data
  browser, project detail, and PDB upload.
- `src/components/chat/` contains the streaming chat layout, message rendering,
  tool cards, and Wiki publish toolbar.
- `src/components/analysis/` contains typed display cards for tool results,
  including annotation, catalytic-site, mutation-score, MD, and benchmark views.
- `src/stores/` contains Zustand auth and chat state.
- `src/lib/api.ts` is the shared API client for authenticated requests,
  automatic 401 handling, file upload helpers, Wiki APIs, and tool task APIs.
- `src/lib/report.ts` renders HTML/Markdown-style report bodies for publishing.
- `tests/` contains lightweight smoke tests for live/public route behavior.

## Auth Behavior

The frontend treats cookies as the source of truth for browser sessions. Local
tokens may be present, but protected routes and API calls rely on `checkAuth()`
and backend cookie recovery rather than assuming local storage is authoritative.

Relevant rules:

- API requests should go through `request`, `authFetch`, or the exported `api`
  helpers in `src/lib/api.ts`.
- Uploads should use the shared upload helper so progress reporting and 401
  recovery stay consistent.
- Pages should not call protected APIs until auth initialization is complete.
- Login checks may recover a valid server-side cookie session and redirect away
  from `/login`.

## Wiki/OIDC Embed

`WikiPage` embeds Outline under `/wiki` and uses `/wiki/auth/oidc` as the stable
entrypoint for the OIDC redirect chain. During iframe loads, these transient
paths are expected and should not be treated as Wiki load failures:

- `/wiki/auth/oidc`
- `/api/oidc/authorize`
- `/wiki/auth/oidc.callback`

Stable embedded Wiki paths include `/wiki/home`, `/wiki/collection/`,
`/wiki/doc/`, and `/wiki/search`.

## PDB And MD Flow

`PDBUploadPage` supports:

- PDB upload and server-side structure analysis.
- 3D structure display via `ProteinViewer`.
- Direct async `gromacs_md` submission through `api.submitTool`.
- Polling task status through `api.getToolTask`.
- Active MD cancellation through `api.cancelToolTask`.
- Rendering successful or failed MD results through `MDResultView`.
- Artifact manifest rendering for structures, topology, trajectory, analysis,
  parameters, and logs.

The page clears stale MD polling timers and result state before starting a new
analysis or resetting the upload, so old task states do not pollute new results.
Cancellation requests also stop the active polling loop and show the returned
`cancel_requested_at` timestamp.

Default MD submission parameters are intentionally short and CPU conservative:

- `simulation_time_ns: 0.01`
- `equilibration_ps: 10.0`
- `ensemble: "nvt"`
- `mdrun_threads: 1`

## Smoke Tests

The frontend includes Playwright-based smoke scripts for route and runtime
checks:

```bash
node tests/public-smoke.mjs
node tests/live-smoke.mjs
node tests/smoke-check.mjs
```

These scripts expect a running stack, usually through `docker compose` and the
public app URL on `http://localhost:4200`.

## Build Notes

`3dmol` is copied from `node_modules` into `public/vendor/3Dmol.js` before dev,
preview, and production builds. The viewer loads that pinned local file at
runtime so Vite does not bundle or scan the dependency's internal `eval` helper.
