import assert from "node:assert/strict";
import test from "node:test";

import { llmsText } from "../app/lib/llms.ts";

const SITE = new URL("https://memiro.ru");

function fakeApi() {
  return {
    categories: async () => ({ items: [{ slug: "zerkala", name: "Зеркала" }], total: 1, page: 1 }),
    landings: async () => ({ items: [{ slug: "zerkala-s-podsvetkoy", heading: "Зеркала с подсветкой" }], total: 1, page: 1 }),
  };
}

test("the document opens with the studio and says what it makes", async () => {
  const text = await llmsText(SITE, fakeApi());
  assert.ok(text !== null);
  assert.ok(text.startsWith("# Memiro"));
  assert.ok(text.includes("Санкт-Петербург"));
});

test("categories and landings are read from the catalogue, not typed out", async () => {
  const text = await llmsText(SITE, fakeApi());
  assert.ok(text !== null);
  assert.ok(text.includes("[Зеркала](https://memiro.ru/catalog/zerkala/)"));
  assert.ok(text.includes("[Зеркала с подсветкой](https://memiro.ru/zerkala-s-podsvetkoy/)"));
});

test("every address is absolute and belongs to the contour's origin", async () => {
  const text = await llmsText(new URL("https://staging.memiro.ru"), fakeApi());
  assert.ok(text !== null);
  assert.ok(!text.includes("https://memiro.ru"));
  assert.ok(text.includes("https://staging.memiro.ru/contacts/"));
});

test("a contour without an origin has no document to give", async () => {
  assert.equal(await llmsText(undefined, fakeApi()), null);
});
