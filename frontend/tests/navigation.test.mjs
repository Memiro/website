import assert from "node:assert/strict";
import { existsSync } from "node:fs";
import test from "node:test";
import { fileURLToPath } from "node:url";

import { isCurrentPath, SITE_LINKS } from "../app/lib/navigation.ts";

function pageFileFor(href) {
  return fileURLToPath(new URL(`../app/pages${href}index.astro`, import.meta.url));
}

test("every link the header and the footer show points at a page that exists", () => {
  for (const link of SITE_LINKS) {
    assert.ok(existsSync(pageFileFor(link.href)), `${link.href} has no page behind it`);
  }
});

test("the catalogue link is current on a product page", () => {
  assert.equal(isCurrentPath("/catalog/mirrors/lira/", "/catalog/"), true);
});

test("the catalogue link is current on a path written without a trailing slash", () => {
  assert.equal(isCurrentPath("/catalog", "/catalog/"), true);
});

test("the catalogue link is not current on the home page", () => {
  assert.equal(isCurrentPath("/", "/catalog/"), false);
});

test("the catalogue link is not current on a page whose address merely starts alike", () => {
  assert.equal(isCurrentPath("/catalogue-of-something/", "/catalog/"), false);
});

test("the home link is current only on the home page, not on every page beneath it", () => {
  assert.equal(isCurrentPath("/", "/"), true);
  assert.equal(isCurrentPath("/catalog/", "/"), false);
});
