import assert from "node:assert/strict";
import test from "node:test";

import { STATIC_PATHS, sitemapEntries, sitemapXml } from "../app/lib/sitemap.ts";

const SITE = new URL("https://memiro.ru");

/** A catalogue of two categories, three products and one landing, paged two at a time. */
function fakeApi() {
  const products = {
    mirrors: [
      [
        { slug: "kolo", name: "Кольцо", price_from: "8900.00", image_keys: ["kolo-front.jpg", "kolo-side.jpg"] },
        { slug: "echo", name: "Эхо", price_from: null, image_keys: [] },
      ],
      [{ slug: "nave", name: "Неф & Co", price_from: "12000.00", image_keys: ["nave.jpg"] }],
    ],
    lights: [[{ slug: "halo", name: "Гало", price_from: "5000.00", image_keys: ["halo.jpg"] }]],
  };
  return {
    categories: async () => ({ items: [{ slug: "mirrors", name: "Зеркала" }, { slug: "lights", name: "Свет" }], total: 2, page: 1 }),
    landings: async () => ({ items: [{ slug: "zerkala-s-podsvetkoy" }], total: 1, page: 1 }),
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
  const xml = sitemapXml(SITE, [{ path: "/", images: [] }, { path: "/catalog/", images: [] }]);
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
  assert.ok(xml.includes("<url><loc>https://memiro.ru/catalog/mirrors/echo/</loc></url>"));
});

test("a contour without an origin has no sitemap to give", () => {
  assert.equal(sitemapXml(undefined, [{ path: "/", images: [] }]), null);
});
