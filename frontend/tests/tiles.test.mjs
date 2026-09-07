import assert from "node:assert/strict";
import test from "node:test";

import { categoryTiles, landingsOfCategory, landingTiles } from "../app/lib/tiles.ts";

const MIRRORS = { name: "Зеркала", slug: "zerkala" };
const CABINETS = { name: "Шкафы", slug: "shkafy" };
const ROUND = { slug: "kruglye-zerkala", heading: "Круглые зеркала", category_slug: "zerkala" };
const BACKLIT = { slug: "zerkala-s-podsvetkoy", heading: "Зеркала с подсветкой", category_slug: "zerkala" };
const MIRRORED_DOOR = { slug: "shkafy-s-zerkalom", heading: "Шкафы с зеркалом", category_slug: "shkafy" };

/**
 * @param {import("../app/lib/catalog-api.ts").LandingSummary[]} landings
 * @param {import("../app/lib/catalog-api.ts").Category[]} categories
 * @returns {import("../app/lib/tiles.ts").TileSource}
 */
function api(landings, categories) {
  return {
    landings: async () => ({ items: landings, total: landings.length, page: 1 }),
    categories: async () => ({ items: categories, total: categories.length, page: 1 }),
  };
}

test("the home page shows the landings the owner wrote", async () => {
  const tiles = await landingTiles(api([ROUND, BACKLIT], [MIRRORS]));

  assert.deepEqual(tiles, [
    { href: "/kruglye-zerkala/", label: "Круглые зеркала" },
    { href: "/zerkala-s-podsvetkoy/", label: "Зеркала с подсветкой" },
  ]);
});

test("with no landing written the home page falls back to the sections", async () => {
  const tiles = await landingTiles(api([], [MIRRORS]));

  assert.deepEqual(tiles, [{ href: "/catalog/zerkala/", label: "Зеркала" }]);
});

test("the root of the catalogue keeps its own structure: the sections", async () => {
  const tiles = await categoryTiles(api([ROUND], [MIRRORS, CABINETS]));

  assert.deepEqual(tiles, [
    { href: "/catalog/zerkala/", label: "Зеркала" },
    { href: "/catalog/shkafy/", label: "Шкафы" },
  ]);
});

test("a section shows its own landings and nobody else's", () => {
  const chips = landingsOfCategory([ROUND, MIRRORED_DOOR, BACKLIT], "zerkala");

  assert.deepEqual(chips, [
    { href: "/kruglye-zerkala/", label: "Круглые зеркала" },
    { href: "/zerkala-s-podsvetkoy/", label: "Зеркала с подсветкой" },
  ]);
});
