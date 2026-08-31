# Catalog and Calculator Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build SSR catalogue and product pages with a legacy-design-compatible Vue calculator whose price always comes from the API.

**Architecture:** Astro pages fetch catalogue data server-side through a typed internal API client; browser-side calculator requests stay relative to `/api`. Pure calculator state and verdict-to-presentation logic live in a framework-free module so Node's built-in test runner can drive a strict red–green seam without adding a dependency. Astro components and the Vue island consume those types and reproduce the former Django storefront's composition and CSS tokens.

**Tech Stack:** Astro 7 SSR, Vue 3, TypeScript strict mode, Node 24 built-in test runner, Docker Compose, FastAPI public API.

**Spec:** `docs/superpowers/specs/2026-08-31-catalog-calculator-design.md`

## Global Constraints

- Do not add dependencies, use `any`, suppress TypeScript errors, add global state, or add authentication.
- Public copy is Russian; TypeScript, comments, and docstrings are English.
- `main:src/memiro/static/css/site.css` and its catalogue templates are the visual source of truth; do not retain the skeleton's Arial or warm palette.
- `GET` requests made by Astro use `API_INTERNAL_URL=http://api:8000`; Vue uses only relative `/api`.
- The public price response may expose only `verdict`, `total`, named selection deltas, and a size threshold; it must never render rates, factors, or calculation lines.
- The calculator island is `client:visible`; all mutable configuration belongs to that island.
- Use red–green TDD for every new behaviour. Run `npm run test`, `npm run check`, and `npm run build` before the final repository recipes.

---

## File Structure

- `frontend/src/lib/catalog-api.ts` — public API DTOs, SSR request client, request errors, and relative calculator request.
- `frontend/src/lib/calculator-state.ts` — framework-free configuration creation, variant application, calculator request creation, and verdict presentation.
- `frontend/tests/catalog-api.test.ts` — real local HTTP-server tests for the SSR client.
- `frontend/tests/calculator-state.test.ts` — Node tests for variant opening and verdicts.
- `frontend/src/components/SiteHeader.astro` and `SiteFooter.astro` — legacy Django shell composition.
- `frontend/src/components/CatalogCard.astro` — whole-card product link with legacy visual structure.
- `frontend/src/components/ProductGallery.astro` — static product-photo presentation.
- `frontend/src/islands/Calculator.vue` — local reactive UI, API submission, deltas, and verdict messages.
- `frontend/src/pages/catalog/index.astro`, `[categorySlug]/index.astro`, and `[categorySlug]/[productSlug]/index.astro` — SSR catalogue routes.
- `frontend/public/fonts/*.woff2` and `frontend/src/styles/global.css` — self-hosted font assets and legacy CSS system.
- `frontend/package.json`, `docker/docker-compose.yml` — test command and SSR API environment.

### Task 1: Create the test seam and calculator state

**Files:**

- Create: `frontend/tests/calculator-state.test.ts`
- Create: `frontend/src/lib/calculator-state.ts`
- Modify: `frontend/package.json`

**Interfaces:**

- Produces `initialCalculatorState(product: ProductCard): CalculatorState`.
- Produces `toCalculateRequest(productId: string, state: CalculatorState): CalculateRequest`.
- Produces `pricePresentation(result: CalculatedPrice): PricePresentation`.
- `Calculator.vue` consumes all three interfaces in Task 4.

- [ ] **Step 1: Write the failing state test**

```ts
import assert from "node:assert/strict";
import test from "node:test";

import { initialCalculatorState, pricePresentation } from "../src/lib/calculator-state.ts";

test("the first product variant opens the calculator with its size and overrides", () => {
  const state = initialCalculatorState({
    id: "mirror", attributes: [], variants: [
      { width_mm: 800, height_mm: 600, price: "8900", overrides: [
        { attribute_id: "blade", value_id: "graphite", quantity: null },
      ] },
    ],
  });

  assert.deepEqual(state, {
    widthMm: 800, heightMm: 600,
    selections: [{ attributeId: "blade", valueId: "graphite", quantity: null }],
  });
});

test("a beyond-limits result invites the customer to leave a wish without a price", () => {
  assert.deepEqual(pricePresentation({ verdict: "BEYOND_LIMITS", total: null, selection_deltas: [] }), {
    kind: "wish", total: null, message: "Этот размер изготовим по индивидуальному пожеланию.",
  });
});
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `node --test --experimental-strip-types frontend/tests/calculator-state.test.ts`

Expected: FAIL because `frontend/src/lib/calculator-state.ts` does not exist.

- [ ] **Step 3: Implement the minimal pure state module**

```ts
export function initialCalculatorState(product: ProductCard): CalculatorState {
  const variant = product.variants[0];
  return {
    widthMm: variant.width_mm,
    heightMm: variant.height_mm,
    selections: variant.overrides.map(toSelection),
  };
}

export function pricePresentation(result: CalculatedPrice): PricePresentation {
  switch (result.verdict) {
    case "BEYOND_LIMITS":
      return { kind: "wish", total: null, message: "Этот размер изготовим по индивидуальному пожеланию." };
    case "HIDDEN":
      return { kind: "hidden", total: null, message: "Стоимость этой конфигурации уточнит менеджер." };
    case "NOT_PRICEABLE":
      return { kind: "unavailable", total: null, message: "Эту конфигурацию пока нельзя рассчитать." };
    case "PRICED":
      return { kind: "priced", total: result.total, message: null };
  }
}
```

Define every DTO locally in this module until Task 2 moves their shared forms to `catalog-api.ts`; do not import Vue.

- [ ] **Step 4: Re-run the focused test and add the package script**

Run: `node --test --experimental-strip-types frontend/tests/calculator-state.test.ts`

Expected: PASS.

Then add `"test": "node --test --experimental-strip-types tests/*.test.ts"` to `frontend/package.json` and run `npm run test` from `frontend/`.

- [ ] **Step 5: Commit the tested seam**

```bash
git add frontend/package.json frontend/src/lib/calculator-state.ts frontend/tests/calculator-state.test.ts
git commit -m "test(frontend): добавь состояние калькулятора"
```

### Task 2: Add the typed public API client

**Files:**

- Create: `frontend/tests/catalog-api.test.ts`
- Create: `frontend/src/lib/catalog-api.ts`
- Modify: `frontend/src/lib/calculator-state.ts`

**Interfaces:**

- Produces `CatalogApi(baseUrl: string)` with `categories()`, `categoryProducts(slug)`, and `product(slug)`.
- Produces `calculate(request: CalculateRequest): Promise<CalculatedPrice>` using relative `/api/calculate` for the browser.
- Produces shared `ProductCard`, `CalculatedPrice`, and `CalculateRequest` types used by Tasks 1, 3, and 4.

- [ ] **Step 1: Write a failing SSR-client test against a real local server**

```ts
test("the SSR client requests a product from its internal API base URL", async (t) => {
  const server = createServer((request, response) => {
    assert.equal(request.url, "/catalog/products/lira");
    response.setHeader("content-type", "application/json");
    response.end(JSON.stringify(productFixture));
  }).listen(0);
  t.after(() => server.close());

  const api = new CatalogApi(`http://127.0.0.1:${address(server).port}`);
  assert.deepEqual(await api.product("lira"), productFixture);
});
```

- [ ] **Step 2: Run the focused test to verify it fails**

Run: `node --test --experimental-strip-types frontend/tests/catalog-api.test.ts`

Expected: FAIL because `CatalogApi` is not exported from `catalog-api.ts`.

- [ ] **Step 3: Implement request and response handling**

```ts
export class CatalogApi {
  public constructor(private readonly baseUrl: string) {}

  public async product(slug: string): Promise<ProductCard> {
    return this.get<ProductCard>(`/catalog/products/${encodeURIComponent(slug)}`);
  }

  private async get<T>(path: string): Promise<T> {
    const response = await fetch(new URL(path, this.baseUrl));
    if (!response.ok) throw new ApiResponseError(response.status);
    return response.json() as Promise<T>;
  }
}
```

Define `categories()` as `get<Category[]>("/catalog/categories")` and
`categoryProducts(slug)` as
`get<ProductSummary[]>(`/catalog/categories/${encodeURIComponent(slug)}/products`)`.
Define `ApiResponseError` with a public numeric `status`. Export
`calculate(request)` that calls `fetch("/api/calculate", { method: "POST",
headers: { "content-type": "application/json" }, body: JSON.stringify(request) })`,
raises the same error on a non-2xx response, and returns `CalculatedPrice`.
Keep response shapes exact to the FastAPI DTOs and do not model any hidden
pricing fields.

- [ ] **Step 4: Run both Node tests**

Run: `npm run test` from `frontend/`

Expected: PASS with both API and calculator-state test files.

- [ ] **Step 5: Commit the client**

```bash
git add frontend/src/lib/catalog-api.ts frontend/src/lib/calculator-state.ts frontend/tests/catalog-api.test.ts
git commit -m "feat(frontend): добавь клиент публичного каталога"
```

### Task 3: Port legacy shell, assets, SSR pages, and catalogue cards

**Files:**

- Create: `frontend/public/fonts/golos-text-cyrillic.woff2`
- Create: `frontend/public/fonts/golos-text-cyrillic-ext.woff2`
- Create: `frontend/public/fonts/golos-text-latin.woff2`
- Create: `frontend/public/fonts/golos-text-latin-ext.woff2`
- Create: `frontend/src/components/SiteHeader.astro`
- Create: `frontend/src/components/SiteFooter.astro`
- Create: `frontend/src/components/CatalogCard.astro`
- Create: `frontend/src/components/ProductGallery.astro`
- Create: `frontend/src/pages/catalog/index.astro`
- Create: `frontend/src/pages/catalog/[categorySlug]/index.astro`
- Modify: `frontend/src/layouts/BaseLayout.astro`
- Modify: `frontend/src/styles/global.css`

**Interfaces:**

- Consumes `CatalogApi` and `ProductSummary` from Task 2.
- Produces SSR HTML for catalogue routes and shared components used by Task 4's product page.

- [ ] **Step 1: Write the failing Astro page imports**

Create the two route files with imports of `CatalogApi`, `SiteHeader`, and `CatalogCard`, then run the type checker before adding those modules.

```astro
---
import { CatalogApi } from "../../lib/catalog-api";
import CatalogCard from "../../components/CatalogCard.astro";

const api = new CatalogApi(import.meta.env.API_INTERNAL_URL);
const categories = await api.categories();
---
```

- [ ] **Step 2: Verify the routes are red**

Run: `npm run check` from `frontend/`

Expected: FAIL because the imports and API methods do not yet exist at this route path.

- [ ] **Step 3: Port the static shell and catalogue UI minimally**

Copy the four Golos font files from `main:src/memiro/static/fonts/` into `frontend/public/fonts/`. Port the tokens, reset, typography, `.wrap`, `.nav`, `.footer`, `.grid-3`, `.product-card`, focus states, and legacy media queries from `main:src/memiro/static/css/site.css`. Build `SiteHeader`, `SiteFooter`, and `CatalogCard` from the matching legacy templates; a card remains one full link to `/catalog/${categorySlug}/${product.slug}/` and omits price markup when `price_from` is `null`.

Implement `CatalogApi.categories()` and `categoryProducts()` if they were not completed in Task 2. The root page renders categories, and the category page renders API products; map `ApiResponseError(404)` to `Astro.redirect("/404")` only after adding a local 404 page, otherwise use Astro's standard `Astro.response.status = 404` template.

- [ ] **Step 4: Verify the SSR routes are green**

Run: `npm run check && npm run build` from `frontend/`

Expected: PASS; build output contains all three SSR route patterns.

- [ ] **Step 5: Commit the SSR catalogue slice**

```bash
git add frontend/public/fonts frontend/src/components frontend/src/layouts/BaseLayout.astro frontend/src/pages/catalog frontend/src/styles/global.css
git commit -m "feat(frontend): добавь SSR-каталог"
```

### Task 4: Build the legacy-compatible product card and calculator island

**Files:**

- Create: `frontend/src/pages/catalog/[categorySlug]/[productSlug]/index.astro`
- Create: `frontend/src/islands/Calculator.vue`
- Modify: `frontend/src/components/ProductGallery.astro`
- Modify: `frontend/src/styles/global.css`
- Modify: `frontend/tests/calculator-state.test.ts`

**Interfaces:**

- Consumes `CatalogApi.product(slug)`, `ProductCard`, `initialCalculatorState`, `toCalculateRequest`, and `pricePresentation`.
- Produces the product SSR card and `client:visible` calculator behaviour.

- [ ] **Step 1: Add failing tests for hidden and priced presentation**

```ts
test("a hidden price replaces monetary output with the manager message", () => {
  assert.deepEqual(pricePresentation({ verdict: "HIDDEN", total: null, selection_deltas: [] }), {
    kind: "hidden", total: null, message: "Стоимость этой конфигурации уточнит менеджер.",
  });
});

test("a priced response retains only its total and selected deltas", () => {
  assert.equal(pricePresentation({ verdict: "PRICED", total: "10100", selection_deltas: [] }).total, "10100");
});
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `npm run test` from `frontend/`

Expected: FAIL until `pricePresentation` supports `HIDDEN` and `PRICED`.

- [ ] **Step 3: Extend the pure module, then implement the island**

Implement the two tested presentations. In `Calculator.vue`, receive `product: ProductCard`, initialise from `initialCalculatorState(product)`, allow dimensions and public declared values to change, submit `toCalculateRequest(product.id, state)`, and render the `PricePresentation`. Map each delta identifier back to a public attribute/value name before displaying `«Подсветка +11 500 ₽»`; never render internal inputs or raw identifiers. Render `BEYOND_LIMITS`, `HIDDEN`, and `NOT_PRICEABLE` as the messages defined by `pricePresentation`.

The Astro product page obtains the product through `CatalogApi`, renders the legacy `.pdp`, gallery, description, `price_from`, and owner-ordered variant table, then mounts `<Calculator client:visible product={product} />`. Use `ProductGallery` for image keys; no storage path assumptions belong in a component.

- [ ] **Step 4: Re-run behaviour and frontend checks**

Run: `npm run test && npm run check && npm run build` from `frontend/`

Expected: PASS; no TypeScript suppression, no `any`, and no price-internal field in the generated source.

- [ ] **Step 5: Commit the product slice**

```bash
git add frontend/src/islands/Calculator.vue frontend/src/pages/catalog/[categorySlug]/[productSlug]/index.astro frontend/src/components/ProductGallery.astro frontend/src/lib/calculator-state.ts frontend/src/styles/global.css frontend/tests/calculator-state.test.ts
git commit -m "feat(frontend): добавь карточку и калькулятор"
```

### Task 5: Configure the contour and perform the vertical-slice verification

**Files:**

- Modify: `docker/docker-compose.yml`
- Modify: `.scratch/rewrite/issues/14-catalog-pages-calculator-island.md`

**Interfaces:**

- Produces `API_INTERNAL_URL=http://api:8000` for Astro SSR and leaves the browser contract at `/api`.

- [ ] **Step 1: Write the failing contour expectation**

Add a focused e2e assertion that an HTTP request to the nginx catalogue route returns SSR markup identifying the requested category/product. Use the real contour and production API; do not add a test-only route or fake the API.

- [ ] **Step 2: Run the e2e test to verify it fails**

Run: `just test-e2e`

Expected: FAIL because the frontend container does not receive `API_INTERNAL_URL` or the SSR route is absent.

- [ ] **Step 3: Add the internal API environment variable and complete the e2e assertion**

```yaml
frontend:
  environment:
    API_INTERNAL_URL: http://api:8000
```

Extend the existing e2e setup only with production-style data seeding necessary to request a published product. Assert visible name and a calculator hydration marker; do not assert private pricing data.

- [ ] **Step 4: Run final verification**

Run, in this order:

```bash
cd frontend && npm run test && npm run check && npm run build
cd .. && just lint && just static && just test && just test-e2e
```

Expected: every command exits 0. Inspect the rendered HTML and public calculate response once to confirm rate, factor, and internal line names are absent.

- [ ] **Step 5: Update ticket and commit**

Mark every acceptance checkbox in issue 14 complete, append exact verification results under `## Comments`, then commit:

```bash
git add docker/docker-compose.yml tests/e2e .scratch/rewrite/issues/14-catalog-pages-calculator-island.md
git commit -m "chore(frontend): настрой SSR-контур каталога"
```

## Plan Self-Review

- Spec coverage: Tasks 2–3 implement SSR routes and internal/public API separation; Tasks 1 and 4 implement initial-variant state, current server price, deltas, and all four verdicts; Tasks 3–4 preserve the Django visual system; Task 5 verifies the live contour and updates the ticket.
- Placeholder scan: no deferred or unspecified implementation steps remain; each task names its files, inputs, outputs, tests, verification command, and commit.
- Type consistency: `ProductCard`, `CalculatedPrice`, `CalculateRequest`, `CalculatorState`, `initialCalculatorState`, `toCalculateRequest`, and `pricePresentation` are defined by Tasks 1–2 before Tasks 3–4 consume them.
