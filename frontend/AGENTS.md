# AGENTS.md

Rules for work inside `frontend/`.

## Boundaries

- This directory is an Astro SSR storefront. It must not become an SSG build.
- TypeScript, comments and docstrings must be English. Public storefront copy is Russian.
- Keep page state local to the island that owns it. Pinia and authentication are not part of this project.
- Put interactive Vue components in `src/islands/` and declare the hydration directive at the Astro call site.
- Keep server-only helpers in `src/lib/`, reusable presentation in `src/components/`, layouts in `src/layouts/`, pages in `src/pages/`, and global CSS in `src/styles/`.
- Do not use `any`, suppress type errors, or add dependencies without the owner's approval.

## Commands

- `npm run dev` starts Astro locally.
- `npm run check` performs Astro and TypeScript validation.
- `npm run build` produces the SSR bundle.
- `npm run start` starts the built Node server.
- `just up` starts the complete local contour; nginx exposes it on the configured host port.

## Before every commit

1. Run `npm run check`.
2. Run `npm run build`.
3. Run the repository checks required by the root `AGENTS.md` for every changed Python or contour file.
