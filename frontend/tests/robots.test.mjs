import assert from "node:assert/strict";
import test from "node:test";

import { AI_CRAWLERS, CLEAN_PARAMS, robotsText } from "../app/lib/robots.ts";

const SITE = new URL("https://memiro.ru");
const text = robotsText(SITE);
const lines = text.split("\n").map((line) => line.trim());

test("the sitemap is announced at the origin the build was given, not a literal", () => {
  assert.ok(lines.includes("Sitemap: https://memiro.ru/sitemap.xml"));
  assert.ok(robotsText(new URL("https://staging.memiro.ru")).includes("Sitemap: https://staging.memiro.ru/sitemap.xml"));
});

test("a contour without an origin announces no sitemap rather than a broken one", () => {
  assert.ok(!robotsText(undefined).includes("Sitemap:"));
});

test("what has nothing to index is closed and the photographs stay open", () => {
  for (const path of ["/cart/", "/api/", "/admin/", "/admin-static/"]) {
    assert.ok(lines.includes(`Disallow: ${path}`), `${path} is open`);
  }
  assert.ok(!text.includes("Disallow: /media/"));
});

// Clean-param is the half of ADR-0003 the code never shipped: Yandex is told
// the narrowings show the same category under another address.
test("narrowing parameters are declared to Yandex and the page number is not", () => {
  assert.deepEqual(CLEAN_PARAMS, ["value", "price_min", "price_max", "sort"]);
  assert.ok(lines.includes(`Clean-param: ${CLEAN_PARAMS.join("&")}`));
});

test("paging is never disallowed: it is the path to the products past the first page", () => {
  assert.ok(!text.includes("page"));
});

test("no AI crawler is refused", () => {
  assert.ok(AI_CRAWLERS.includes("ClaudeBot") && AI_CRAWLERS.includes("GPTBot"));
  for (const crawler of AI_CRAWLERS) {
    assert.ok(lines.includes(`User-agent: ${crawler}`), `${crawler} is not named`);
  }
  assert.equal(text.match(/^Disallow: \/$/gm), null);
});

// Yandex retired Host in 2018; the legacy WordPress robots.txt still carries it.
test("the retired Host directive is not carried over", () => {
  assert.ok(!text.includes("Host:"));
});

// A named group replaces the `*` group outright: an AI crawler given only
// "Allow: /" would be handed /cart/, /api/ and the admin.
test("an AI crawler is allowed the site but not what is closed to everyone", () => {
  const groups = text.split("\n\n");
  for (const crawler of AI_CRAWLERS) {
    const group = groups.find((block) => block.startsWith(`User-agent: ${crawler}`));
    assert.ok(group !== undefined, `${crawler} has no group`);
    for (const path of ["/cart/", "/api/", "/admin/", "/admin-static/"]) {
      assert.ok(group.includes(`Disallow: ${path}`), `${crawler} is handed ${path}`);
    }
    assert.ok(group.includes("Allow: /"));
  }
});
