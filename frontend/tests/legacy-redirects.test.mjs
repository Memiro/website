import assert from "node:assert/strict";
import fs from "node:fs";
import test from "node:test";

import { GONE_PATHS, legacyResponse, redirectTarget } from "../app/lib/legacy-redirects.ts";

/** Every address the WordPress sitemap index published on 2026-09-08. */
const LEGACY = fs.readFileSync(new URL("./legacy-urls.txt", import.meta.url), "utf8")
  .split("\n").filter((line) => line !== "").map((url) => url.replace("https://memiro.ru", ""));

// The list is the specification: an address nobody thought about must be red
// here, not a silent 404 on the day the domain switches.
test("every address the old site published is answered deliberately", () => {
  assert.equal(LEGACY.length, 97);
  for (const path of LEGACY) {
    const answer = legacyResponse(path);
    const handled = answer !== null || ["/", "/catalog/", "/contacts/"].includes(path);
    assert.ok(handled, `${path} would simply 404`);
  }
});

test("a product keeps its slug and gains its category", () => {
  assert.deepEqual(legacyResponse("/mirrors/krugloe-zerkalo-kolo/"), {
    status: 301,
    location: "/catalog/zerkala/krugloe-zerkalo-kolo/",
  });
});

test("the pages that only changed address move with 301", () => {
  assert.deepEqual(legacyResponse("/about-us/"), { status: 301, location: "/about/" });
  assert.deepEqual(legacyResponse("/delivery-payment-and-services/"), { status: 301, location: "/delivery/" });
  assert.deepEqual(legacyResponse("/privacy-policy/"), { status: 301, location: "/privacy/" });
});

test("addresses that survived the move are left alone", () => {
  for (const path of ["/", "/catalog/", "/contacts/"]) {
    assert.equal(legacyResponse(path), null);
  }
});

// 410 tells the truth and clears the address faster than a 404; a redirect to
// the listing would be read as a soft 404 and save nothing (ADR-0015).
test("what no longer exists is gone, not redirected to a listing", () => {
  for (const path of GONE_PATHS) {
    assert.deepEqual(legacyResponse(path), { status: 410, location: null });
  }
  assert.ok(GONE_PATHS.includes("/privet-mir/"));
});

test("a missing trailing slash is the same address", () => {
  assert.deepEqual(legacyResponse("/mirrors/krugloe-zerkalo-kolo"), {
    status: 301,
    location: "/catalog/zerkala/krugloe-zerkalo-kolo/",
  });
});

test("no redirect lands on an address that redirects again", () => {
  for (const path of LEGACY) {
    const answer = legacyResponse(path);
    if (answer?.location != null) {
      assert.equal(legacyResponse(answer.location), null, `${path} starts a chain`);
    }
  }
});

test("nothing outside the old site is touched", () => {
  assert.equal(legacyResponse("/catalog/zerkala/krugloe-zerkalo-kolo/"), null);
  assert.equal(legacyResponse("/works/"), null);
});

test("a redirect keeps the query the visitor arrived with", () => {
  assert.equal(
    redirectTarget("/catalog/zerkala/kolo/", "?utm_source=yandex"),
    "/catalog/zerkala/kolo/?utm_source=yandex",
  );
  assert.equal(redirectTarget("/catalog/zerkala/kolo/", ""), "/catalog/zerkala/kolo/");
});
