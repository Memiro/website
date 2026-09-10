import assert from "node:assert/strict";
import test from "node:test";

import {
  catalogSearch,
  isBeyondLastPage,
  isNarrowed,
  parseCatalogQuery,
  withPage,
  withoutPrice,
  withoutValue,
  withSort,
} from "../app/lib/catalog-query.ts";

const ROUND = "1f7a1d4e-3c0b-4d2a-9c6e-8a1b2c3d4e5f";
const BLACK = "2a8b2e5f-4d1c-4e3b-8d7f-9b2c3d4e5f60";

function query(search) {
  return parseCatalogQuery(new URLSearchParams(search));
}

test("a repeated value parameter is read as several chosen rows", () => {
  assert.deepEqual(query(`value=${ROUND}&value=${BLACK}`).values, [ROUND, BLACK]);
});

test("a value that is not shaped like an identifier is dropped before the API sees it", () => {
  assert.deepEqual(query("value=1").values, []);
  assert.deepEqual(query("value=").values, []);
  assert.deepEqual(query("value=cvet:chernyy").values, []);
  assert.deepEqual(query(`value=1&value=${ROUND}`).values, [ROUND]);
});

test("a page that is not a number falls back to the first one", () => {
  assert.equal(query("page=последняя").page, 1);
});

test("a sort the site does not offer falls back to the order by name", () => {
  assert.equal(query("sort=random").sort, "name");
});

test("a price that is not a number is dropped instead of refusing the page", () => {
  assert.equal(query("price_min=дорого").priceMin, "");
});

test("an untouched catalogue asks the API without a query string", () => {
  assert.equal(catalogSearch(query("")), "");
});

test("the API is asked only for what the visitor actually chose", () => {
  assert.equal(catalogSearch(query(`value=${ROUND}&price_min=5000&sort=cheapest&page=2`)), `value=${ROUND}&price_min=5000&sort=cheapest&page=2`);
});

test("dropping a chip keeps the other narrowings and returns to the first page", () => {
  const narrowed = query(`value=${ROUND}&value=${BLACK}&sort=cheapest&page=3`);

  assert.equal(withoutValue("/catalog/mirrors/", narrowed, ROUND), `/catalog/mirrors/?value=${BLACK}&sort=cheapest`);
});

test("dropping the price keeps the chosen rows", () => {
  assert.equal(withoutPrice("/catalog/mirrors/", query(`value=${ROUND}&price_max=9000`)), `/catalog/mirrors/?value=${ROUND}`);
});

test("choosing an order starts the listing again from its first page", () => {
  assert.equal(withSort("/catalog/mirrors/", query("page=4"), "dearest"), "/catalog/mirrors/?sort=dearest");
});

test("a page link keeps every narrowing the visitor made", () => {
  assert.equal(withPage("/catalog/mirrors/", query(`value=${ROUND}`), 2), `/catalog/mirrors/?value=${ROUND}&page=2`);
});

test("the last page is still a page, and the one after it is not", () => {
  assert.equal(isBeyondLastPage(query("page=4"), 4), false);
  assert.equal(isBeyondLastPage(query("page=5"), 4), true);
});

test("an empty listing keeps its first page and nothing past it", () => {
  assert.equal(isBeyondLastPage(query(""), 0), false);
  assert.equal(isBeyondLastPage(query("page=2"), 0), true);
});

test("a listing nobody narrowed is not a filtered page", () => {
  assert.equal(isNarrowed(query("sort=cheapest")), false);
  assert.equal(isNarrowed(query("price_max=9000")), true);
});
