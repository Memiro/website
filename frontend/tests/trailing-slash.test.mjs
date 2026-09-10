import assert from "node:assert/strict";
import test from "node:test";

import { legacyResponse } from "../app/lib/legacy-redirects.ts";
import { slashRedirect } from "../app/lib/trailing-slash.ts";

test("an address without a trailing slash moves to the same address with one", () => {
  assert.equal(slashRedirect("/about"), "/about/");
  assert.equal(slashRedirect("/catalog"), "/catalog/");
  assert.equal(slashRedirect("/catalog/zerkala/aura"), "/catalog/zerkala/aura/");
});

test("an address that already ends with a slash stays where it is", () => {
  assert.equal(slashRedirect("/"), null);
  assert.equal(slashRedirect("/about/"), null);
  assert.equal(slashRedirect("/catalog/zerkala/aura/"), null);
});

test("files, built assets and photographs are not pages and keep their address", () => {
  for (const path of ["/robots.txt", "/sitemap.xml", "/llms.txt", "/yml.xml", "/favicon.ico", "/_astro/x.css", "/media/x.jpg"]) {
    assert.equal(slashRedirect(path), null, path);
  }
});

// The middleware answers the old site first, and that answer already ends
// with a slash: one hop, never a chain of two.
test("an old address without a slash still earns one 301 straight to its new home", () => {
  assert.deepEqual(legacyResponse("/about-us"), { status: 301, location: "/about/" });
  assert.equal(slashRedirect("/about/"), null);
});
