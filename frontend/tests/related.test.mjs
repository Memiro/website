import assert from "node:assert/strict";
import test from "node:test";

import { neighbours, relatedProducts, shapeValueId } from "../app/lib/related.ts";

/** @type {import("../app/lib/catalog-api.ts").ProductAttribute} */
const SHAPE = { id: "attr-shape", name: "Форма", kind: "select", is_customer_changeable: false, declared_value_id: "round", values: [{ id: "round", name: "Круглое", quantity: null }] };
/** @type {import("../app/lib/catalog-api.ts").ProductAttribute} */
const FRAME = { id: "attr-frame", name: "Рама", kind: "select", is_customer_changeable: true, declared_value_id: "none", values: [{ id: "none", name: "Без рамы", quantity: null }] };

/**
 * @param {string} slug
 * @param {import("../app/lib/catalog-api.ts").ProductAttribute[]} attributes
 * @returns {import("../app/lib/catalog-api.ts").ProductCard}
 */
function product(slug, attributes = [SHAPE, FRAME]) {
  return {
    id: slug, name: slug.toUpperCase(), slug, category_slug: "zerkala", category_name: "Зеркала",
    price_from: null, image_keys: [], images: [], description: "", attributes, variants: [], updated_at: "2026-09-01T10:00:00Z",
  };
}

/** @param {string[]} slugs @returns {import("../app/lib/catalog-api.ts").ProductSummary[]} */
function listing(slugs) {
  return slugs.map((slug) => ({ name: slug.toUpperCase(), slug, price_from: null, image_keys: [], images: [], updated_at: "2026-09-01T10:00:00Z" }));
}

test("the shape is the declared row of the attribute named Форма", () => {
  assert.equal(shapeValueId(product("halo")), "round");
});

test("a mirror without a shape attribute has no shape", () => {
  assert.equal(shapeValueId(product("halo", [FRAME])), null);
});

test("neighbours are two after and two before, kept in list order", () => {
  const items = listing(["a", "b", "c", "d", "e", "f", "g"]);

  assert.deepEqual(neighbours(items, "d", 4).map((item) => item.slug), ["b", "c", "e", "f"]);
});

test("a mirror at the end of the list borrows its neighbours from before it", () => {
  const items = listing(["a", "b", "c", "d", "e", "f", "g"]);

  assert.deepEqual(neighbours(items, "g", 4).map((item) => item.slug), ["c", "d", "e", "f"]);
});

test("a mirror at the start of the list takes all its neighbours from after it", () => {
  const items = listing(["a", "b", "c", "d", "e", "f", "g"]);

  assert.deepEqual(neighbours(items, "a", 4).map((item) => item.slug), ["b", "c", "d", "e"]);
});

test("a mirror second in the list keeps its one predecessor and borrows the rest from after", () => {
  const items = listing(["a", "b", "c", "d", "e", "f", "g"]);

  assert.deepEqual(neighbours(items, "b", 4).map((item) => item.slug), ["a", "c", "d", "e"]);
});

test("a mirror missing from the list gives the head of the list", () => {
  const items = listing(["a", "b", "c", "d", "e"]);

  assert.deepEqual(neighbours(items, "zzz", 4).map((item) => item.slug), ["a", "b", "c", "d"]);
});

test("related mirrors are asked from the category narrowed to the same shape", async () => {
  /** @type {string[]} */
  const searches = [];
  /** @type {import("../app/lib/related.ts").CategoryReader} */
  const reader = {
    async categoryProducts(slug, search) {
      searches.push(`${slug}?${search}`);
      return { items: listing(["a", "b", "halo", "c"]), total: 4, page: 1, pages: 1, groups: [], price: null, sort: "name" };
    },
  };

  const related = await relatedProducts(reader, "mirrors", product("halo"));

  assert.deepEqual(searches, ["mirrors?value=round"]);
  assert.deepEqual(related.map((item) => item.slug), ["a", "b", "c"]);
});

test("the listing is walked page by page until the mirror itself is on it", async () => {
  /** @type {Record<number, import("../app/lib/catalog-api.ts").ProductSummary[]>} */
  const pages = { 1: listing(["a", "b"]), 2: listing(["c", "halo", "d", "e"]), 3: listing(["f", "g"]) };
  /** @type {number[]} */
  const asked = [];
  /** @type {import("../app/lib/related.ts").CategoryReader} */
  const reader = {
    async categoryProducts(_slug, search) {
      const page = Number(new URLSearchParams(search).get("page") ?? "1");
      asked.push(page);
      return { items: pages[page] ?? [], total: 8, page, pages: 3, groups: [], price: null, sort: "name" };
    },
  };

  const related = await relatedProducts(reader, "mirrors", product("halo"));

  assert.deepEqual(asked, [1, 2]);
  assert.deepEqual(related.map((item) => item.slug), ["b", "c", "d", "e"]);
});

test("a mirror at the foot of a page gets its successors from the next page", async () => {
  /** @type {Record<number, import("../app/lib/catalog-api.ts").ProductSummary[]>} */
  const pages = { 1: listing(["a", "b", "c", "halo"]), 2: listing(["d", "e", "f", "g"]) };
  /** @type {number[]} */
  const asked = [];
  /** @type {import("../app/lib/related.ts").CategoryReader} */
  const reader = {
    async categoryProducts(_slug, search) {
      const page = Number(new URLSearchParams(search).get("page") ?? "1");
      asked.push(page);
      return { items: pages[page] ?? [], total: 8, page, pages: 2, groups: [], price: null, sort: "name" };
    },
  };

  const related = await relatedProducts(reader, "mirrors", product("halo"));

  assert.deepEqual(asked, [1, 2]);
  assert.deepEqual(related.map((item) => item.slug), ["b", "c", "d", "e"]);
});

test("a mirror absent from its own listing walks every page and gets the head", async () => {
  /** @type {Record<number, import("../app/lib/catalog-api.ts").ProductSummary[]>} */
  const pages = { 1: listing(["a", "b"]), 2: listing(["c", "d"]), 3: listing(["e", "f"]) };
  /** @type {number[]} */
  const asked = [];
  /** @type {import("../app/lib/related.ts").CategoryReader} */
  const reader = {
    async categoryProducts(_slug, search) {
      const page = Number(new URLSearchParams(search).get("page") ?? "1");
      asked.push(page);
      return { items: pages[page] ?? [], total: 6, page, pages: 3, groups: [], price: null, sort: "name" };
    },
  };

  const related = await relatedProducts(reader, "mirrors", product("halo"));

  assert.deepEqual(asked, [1, 2, 3]);
  assert.deepEqual(related.map((item) => item.slug), ["a", "b", "c", "d"]);
});

test("a mirror without a shape gets its plain category neighbours", async () => {
  /** @type {string[]} */
  const searches = [];
  /** @type {import("../app/lib/related.ts").CategoryReader} */
  const reader = {
    async categoryProducts(slug, search) {
      searches.push(`${slug}?${search}`);
      return { items: listing(["halo", "b"]), total: 2, page: 1, pages: 1, groups: [], price: null, sort: "name" };
    },
  };

  const related = await relatedProducts(reader, "mirrors", product("halo", [FRAME]));

  assert.deepEqual(searches, ["mirrors?"]);
  assert.deepEqual(related.map((item) => item.slug), ["b"]);
});
