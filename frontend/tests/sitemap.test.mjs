import assert from "node:assert/strict";
import test from "node:test";

import { STATIC_PATHS, sitemapPaths, sitemapXml } from "../app/lib/sitemap.ts";

const SITE = new URL("https://memiro.ru");

/** A catalogue of two categories, three products and one landing, paged two at a time. */
function fakeApi() {
  const products = {
    mirrors: [[{ slug: "kolo" }, { slug: "echo" }], [{ slug: "nave" }]],
    lights: [[{ slug: "halo" }]],
  };
  return {
    categories: async () => ({ items: [{ slug: "mirrors" }, { slug: "lights" }], total: 2, page: 1 }),
    landings: async () => ({ items: [{ slug: "zerkala-s-podsvetkoy" }], total: 1, page: 1 }),
    categoryProducts: async (slug, search) => {
      const pages = products[slug];
      const page = Number(new URLSearchParams(search).get("page") ?? "1");
      return { items: pages[page - 1] ?? [], pages: pages.length, page, total: 3 };
    },
  };
}

test("every page that may be indexed is listed, and nothing else", async () => {
  const paths = await sitemapPaths(fakeApi());
  assert.deepEqual(paths, [
    ...STATIC_PATHS,
    "/catalog/mirrors/",
    "/catalog/mirrors/kolo/",
    "/catalog/mirrors/echo/",
    "/catalog/mirrors/nave/",
    "/catalog/lights/",
    "/catalog/lights/halo/",
    "/zerkala-s-podsvetkoy/",
  ]);
});

// The listing is paged: asking once would quietly lose the tail of a catalogue
// the moment it outgrows a single page.
test("products past the first page of a category are not lost", async () => {
  const paths = await sitemapPaths(fakeApi());
  assert.ok(paths.includes("/catalog/mirrors/nave/"));
});

test("what is closed to indexing never reaches the sitemap", async () => {
  const paths = await sitemapPaths(fakeApi());
  for (const closed of ["/cart/", "/404", "/500"]) {
    assert.ok(!paths.includes(closed));
  }
  assert.ok(paths.every((path) => !path.includes("?")));
});

test("the document spells absolute addresses and nothing a crawler ignores", () => {
  const xml = sitemapXml(SITE, ["/", "/catalog/"]);
  assert.ok(xml !== null);
  assert.ok(xml.startsWith('<?xml version="1.0" encoding="UTF-8"?>'));
  assert.ok(xml.includes("<loc>https://memiro.ru/catalog/</loc>"));
  assert.ok(!xml.includes("changefreq") && !xml.includes("priority") && !xml.includes("lastmod"));
});

test("a contour without an origin has no sitemap to give", () => {
  assert.equal(sitemapXml(undefined, ["/"]), null);
});
