import assert from "node:assert/strict";
import test from "node:test";

import { MAX_PICTURES, SALES_NOTES, ymlContent, ymlText } from "../app/lib/yml.ts";

const SITE = new URL("https://memiro.ru");
const NOW = new Date("2026-09-10T09:30:00.000Z");
const MANY_PHOTOS = Array.from({ length: MAX_PICTURES + 2 }, (_, index) => `kolo-${index + 1}.jpg`);

/** Two categories; a product with too many photos, one without a price, one without a photo, one with characters XML minds. */
function fakeApi() {
  const products = {
    mirrors: [
      [
        { slug: "kolo", name: "Кольцо", price_from: "8900.00", image_keys: MANY_PHOTOS },
        { slug: "echo", name: "Эхо", price_from: null, image_keys: ["echo.jpg"], updated_at: "2026-09-01T10:00:00Z" },
      ],
      [{ slug: "nave", name: "Неф & Co", price_from: "12000.50", image_keys: ["nave.jpg"], updated_at: "2026-09-01T10:00:00Z" }],
    ],
    lights: [[
      { slug: "halo", name: "Гало", price_from: "5000.00", image_keys: ["halo.jpg"], updated_at: "2026-09-01T10:00:00Z" },
      { slug: "mute", name: "Мьют", price_from: "700.00", image_keys: [], updated_at: "2026-09-01T10:00:00Z" },
    ]],
  };
  const descriptions = { kolo: "Круглое зеркало.", nave: "Полотно <4 мм> в раме \"Loft\".", halo: "Свет." };
  return {
    categories: async () => ({ items: [{ slug: "mirrors", name: "Зеркала & свет", updated_at: "2026-09-01T10:00:00Z" }, { slug: "lights", name: "Свет", updated_at: "2026-09-01T10:00:00Z" }] }),
    categoryProducts: async (slug, search) => {
      const pages = products[slug];
      const page = Number(new URLSearchParams(search).get("page") ?? "1");
      return { items: pages[page - 1] ?? [], pages: pages.length };
    },
    product: async (slug) => {
      const description = descriptions[slug];
      if (description === undefined) {
        throw new Error(`the card of ${slug} was asked for although it feeds nothing`);
      }
      return { description };
    },
  };
}

async function feed() {
  const content = await ymlContent(fakeApi());
  const xml = ymlText(SITE, { name: "Memiro", company: "ИП Иванов", categories: content.categories }, content.offers, NOW);
  assert.ok(xml !== null);
  return xml;
}

test("every product with a price and a photo is an offer, and one missing either feeds nothing", async () => {
  const { offers } = await ymlContent(fakeApi());
  assert.deepEqual(offers.map((offer) => offer.id), ["kolo", "nave", "halo"]);
  assert.deepEqual(offers.map((offer) => offer.categoryId), [1, 1, 2]);
  assert.equal(offers[0].path, "/catalog/mirrors/kolo/");
  assert.equal(offers[0].description, "Круглое зеркало.");
});

test("an offer carries at most as many pictures as the format allows", async () => {
  const { offers } = await ymlContent(fakeApi());
  assert.equal(offers[0].pictures.length, MAX_PICTURES);
  assert.equal(offers[0].pictures[0], "/media/kolo-1.jpg");
});

test("the shop is named with its company, its currency and its numbered categories", async () => {
  const xml = await feed();
  assert.ok(xml.startsWith('<?xml version="1.0" encoding="UTF-8"?>\n<yml_catalog date="2026-09-10T09:30:00+00:00">'));
  assert.ok(xml.includes("<name>Memiro</name>"));
  assert.ok(xml.includes("<company>ИП Иванов</company>"));
  assert.ok(xml.includes("<url>https://memiro.ru/</url>"));
  assert.ok(xml.includes('<currency id="RUB" rate="1"/>'));
  assert.ok(xml.includes('<category id="1">Зеркала &amp; свет</category>'));
  assert.ok(xml.includes('<category id="2">Свет</category>'));
});

test("an offer is available, the way Yandex shows one, with the from price and the note about ordering", async () => {
  const xml = await feed();
  assert.ok(xml.includes('<offer id="kolo" available="true">'));
  assert.ok(xml.includes("<url>https://memiro.ru/catalog/mirrors/kolo/</url>"));
  assert.ok(xml.includes("<price>8900</price>"));
  assert.ok(xml.includes("<price>12000.5</price>"));
  assert.ok(xml.includes("<currencyId>RUB</currencyId>"));
  assert.ok(xml.includes("<categoryId>2</categoryId>"));
  assert.ok(xml.includes("<picture>https://memiro.ru/media/halo.jpg</picture>"));
  assert.ok(xml.includes(`<sales_notes>${SALES_NOTES}</sales_notes>`));
  assert.ok(!xml.includes("echo"));
  assert.ok(!xml.includes("mute"));
});

test("special characters in a name and a description are escaped", async () => {
  const xml = await feed();
  assert.ok(xml.includes("<name>Неф &amp; Co</name>"));
  assert.ok(xml.includes("<description>Полотно &lt;4 мм&gt; в раме &quot;Loft&quot;.</description>"));
});

test("an address with a query character is escaped like any other text", () => {
  const offer = { id: "kolo", path: "/catalog/mirrors/kolo/?a=1&b=2", price: "1", categoryId: 1, pictures: ["/media/a&b.jpg"], name: "K", description: "" };
  const xml = ymlText(SITE, { name: "Memiro", company: "Memiro", categories: [] }, [offer], NOW);
  assert.ok(xml?.includes("<url>https://memiro.ru/catalog/mirrors/kolo/?a=1&amp;b=2</url>"));
  assert.ok(xml?.includes("<picture>https://memiro.ru/media/a&amp;b.jpg</picture>"));
});

test("a contour without an origin has no feed to give", () => {
  assert.equal(ymlText(undefined, { name: "Memiro", company: "Memiro", categories: [] }, [], NOW), null);
});
