# AGENTS.md

Rules for work inside `frontend/`.

## Boundaries

- This directory is an Astro SSR storefront. It must not become an SSG build.
- TypeScript, comments and docstrings must be English. Public storefront copy is Russian.
- Keep page state local to the island that owns it. Pinia and authentication are not part of this project.
- Put interactive Vue components in `app/islands/` and declare the hydration directive at the Astro call site.
- Keep server-only helpers in `app/lib/`, reusable presentation in `app/components/`, layouts in `app/layouts/`, pages in `app/pages/`, and global CSS in `app/styles/`.
- Do not use `any`, suppress type errors, or add dependencies without the owner's approval.
- No narrating comments and no doc-comment ceremony: a comment states only a "why" the code cannot show (an external constraint, a non-obvious decision), never what the next line does. Any doc comment that survives is one line.

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
