import assert from "node:assert/strict";
import test from "node:test";

import { newestDay, STATIC_PATHS, sitemapEntries, sitemapXml } from "../app/lib/sitemap.ts";

const SITE = new URL("https://memiro.ru");

/** A catalogue of two categories, three products and one landing, paged two at a time. */
function fakeApi() {
  const products = {
    mirrors: [
      [
        { slug: "kolo", name: "Кольцо", price_from: "8900.00", image_keys: ["kolo-front.jpg", "kolo-side.jpg"], updated_at: "2026-09-09T10:00:00Z" },
        { slug: "echo", name: "Эхо", price_from: null, image_keys: [], updated_at: "2026-08-01T10:00:00Z" },
      ],
      [{ slug: "nave", name: "Неф & Co", price_from: "12000.00", image_keys: ["nave.jpg"], updated_at: "2026-07-15T10:00:00Z" }],
    ],
    lights: [[{ slug: "halo", name: "Гало", price_from: "5000.00", image_keys: ["halo.jpg"], updated_at: "2026-06-01T10:00:00Z" }]],
  };
  return {
    categories: async () => ({ items: [{ slug: "mirrors", name: "Зеркала", updated_at: "2026-05-01T10:00:00Z" }, { slug: "lights", name: "Свет", updated_at: "2026-05-02T10:00:00Z" }], total: 2, page: 1 }),
    landings: async () => ({ items: [{ slug: "zerkala-s-podsvetkoy", updated_at: "2026-04-20T10:00:00Z" }], total: 1, page: 1 }),
    categoryProducts: async (slug, search) => {
      const pages = products[slug];
      const page = Number(new URLSearchParams(search).get("page") ?? "1");
      return { items: pages[page - 1] ?? [], pages: pages.length, page, total: 3 };
    },
  };
}

async function paths() {
  return (await sitemapEntries(fakeApi())).map((entry) => entry.path);
}

test("every page that may be indexed is listed, and nothing else", async () => {
  assert.deepEqual(await paths(), [
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
  assert.ok((await paths()).includes("/catalog/mirrors/nave/"));
});

test("what is closed to indexing never reaches the sitemap", async () => {
  const listed = await paths();
  for (const closed of ["/cart/", "/404", "/500"]) {
    assert.ok(!listed.includes(closed));
  }
  assert.ok(listed.every((path) => !path.includes("?")));
});

test("a product declares every photograph it has, captioned the way the gallery captions them", async () => {
  const entries = await sitemapEntries(fakeApi());
  const kolo = entries.find((entry) => entry.path === "/catalog/mirrors/kolo/");
  assert.deepEqual(kolo?.images, [
    { path: "/media/kolo-front.jpg", title: "Кольцо" },
    { path: "/media/kolo-side.jpg", title: "Кольцо — фото 2" },
  ]);
});

test("pages that are not a product declare no photographs", async () => {
  const entries = await sitemapEntries(fakeApi());
  for (const path of [...STATIC_PATHS, "/catalog/mirrors/", "/zerkala-s-podsvetkoy/"]) {
    assert.deepEqual(entries.find((entry) => entry.path === path)?.images, []);
  }
});

test("the document spells absolute addresses and nothing a crawler ignores", () => {
  const xml = sitemapXml(SITE, [{ path: "/", images: [], lastmod: null }, { path: "/catalog/", images: [], lastmod: null }]);
  assert.ok(xml !== null);
  assert.ok(xml.startsWith('<?xml version="1.0" encoding="UTF-8"?>'));
  assert.ok(xml.includes("<loc>https://memiro.ru/catalog/</loc>"));
  assert.ok(!xml.includes("changefreq") && !xml.includes("priority") && !xml.includes("lastmod"));
});

test("photographs are declared in the image namespace with absolute addresses and escaped titles", async () => {
  const xml = sitemapXml(SITE, await sitemapEntries(fakeApi()));
  assert.ok(xml !== null);
  assert.ok(xml.includes('xmlns:image="http://www.google.com/schemas/sitemap-image/1.1"'));
  assert.ok(xml.includes("<image:image><image:loc>https://memiro.ru/media/kolo-side.jpg</image:loc><image:title>Кольцо — фото 2</image:title></image:image>"));
  assert.ok(xml.includes("<image:title>Неф &amp; Co</image:title>"));
  assert.equal(xml.match(/<image:image>/g)?.length, 4);
});

test("a product without photographs carries no image element", async () => {
  const xml = sitemapXml(SITE, await sitemapEntries(fakeApi()));
  assert.ok(xml !== null);
  assert.ok(xml.includes("<url><loc>https://memiro.ru/catalog/mirrors/echo/</loc><lastmod>2026-08-01</lastmod></url>"));
});

test("an address with an ampersand is escaped in the document", () => {
  const xml = sitemapXml(SITE, [{ path: "/catalog/a/", images: [{ path: "/media/a&b.jpg", title: "A" }], lastmod: null }]);
  assert.ok(xml?.includes("<image:loc>https://memiro.ru/media/a&amp;b.jpg</image:loc>"));
});

test("a contour without an origin has no sitemap to give", () => {
  assert.equal(sitemapXml(undefined, [{ path: "/", images: [], lastmod: null }]), null);
});


test("a product page is dated by the day its card was last edited", async () => {
  const entries = await sitemapEntries(fakeApi());

  assert.equal(entries.find((entry) => entry.path === "/catalog/mirrors/kolo/")?.lastmod, "2026-09-09");
});

test("a category page is dated by the newest of its own stamp and its products'", async () => {
  const entries = await sitemapEntries(fakeApi());

  assert.equal(entries.find((entry) => entry.path === "/catalog/mirrors/")?.lastmod, "2026-09-09");
});

test("the home page and the catalogue index are as fresh as the freshest row of the catalogue", async () => {
  const entries = await sitemapEntries(fakeApi());

  assert.equal(entries.find((entry) => entry.path === "/")?.lastmod, "2026-09-09");
  assert.equal(entries.find((entry) => entry.path === "/catalog/")?.lastmod, "2026-09-09");
});

test("a page written by hand claims no date, because nothing knows when it changed", async () => {
  const entries = await sitemapEntries(fakeApi());

  for (const path of ["/about/", "/delivery/", "/contacts/", "/privacy/", "/works/"]) {
    assert.equal(entries.find((entry) => entry.path === path)?.lastmod, null);
  }
});

test("a landing is dated by its own stamp", async () => {
  const entries = await sitemapEntries(fakeApi());

  assert.equal(entries.find((entry) => entry.path === "/zerkala-s-podsvetkoy/")?.lastmod, "2026-04-20");
});

test("the document carries the day before the photographs of the same page", async () => {
  const xml = sitemapXml(SITE, await sitemapEntries(fakeApi()));

  assert.ok(xml?.includes("<loc>https://memiro.ru/catalog/mirrors/kolo/</loc><lastmod>2026-09-09</lastmod><image:image>"));
});

test("no date is written where nothing is known, rather than today's", async () => {
  const xml = sitemapXml(SITE, await sitemapEntries(fakeApi()));

  assert.ok(xml?.includes("<url><loc>https://memiro.ru/privacy/</loc></url>"));
});

test("the newest day is picked whatever order the stamps arrive in, and nothing is no day", () => {
  assert.equal(newestDay(["2026-01-05T00:00:00Z", "2026-03-01T23:59:59Z", "2026-02-01T00:00:00Z"]), "2026-03-01");
  assert.equal(newestDay([]), null);
  assert.equal(newestDay(["not a date"]), null);
});
