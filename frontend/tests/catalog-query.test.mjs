import assert from "node:assert/strict";
import test from "node:test";

import {
  catalogSearch,
  isNarrowed,
  parseCatalogQuery,
  withPage,
  withoutPrice,
  withoutValue,
  withSort,
} from "../app/lib/catalog-query.ts";

function query(search) {
  return parseCatalogQuery(new URLSearchParams(search));
}

test("a repeated value parameter is read as several chosen rows", () => {
  assert.deepEqual(query("value=round&value=black").values, ["round", "black"]);
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
  assert.equal(catalogSearch(query("value=round&price_min=5000&sort=cheapest&page=2")), "value=round&price_min=5000&sort=cheapest&page=2");
});

test("dropping a chip keeps the other narrowings and returns to the first page", () => {
  const narrowed = query("value=round&value=black&sort=cheapest&page=3");

  assert.equal(withoutValue("/catalog/mirrors/", narrowed, "round"), "/catalog/mirrors/?value=black&sort=cheapest");
});

test("dropping the price keeps the chosen rows", () => {
  assert.equal(withoutPrice("/catalog/mirrors/", query("value=round&price_max=9000")), "/catalog/mirrors/?value=round");
});

test("choosing an order starts the listing again from its first page", () => {
  assert.equal(withSort("/catalog/mirrors/", query("page=4"), "dearest"), "/catalog/mirrors/?sort=dearest");
});

test("a page link keeps every narrowing the visitor made", () => {
  assert.equal(withPage("/catalog/mirrors/", query("value=round"), 2), "/catalog/mirrors/?value=round&page=2");
});

test("a listing nobody narrowed is not a filtered page", () => {
  assert.equal(isNarrowed(query("sort=cheapest")), false);
  assert.equal(isNarrowed(query("price_max=9000")), true);
});
