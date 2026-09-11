import assert from "node:assert/strict";
import test from "node:test";

import { CARD_SIZES, tileSizes } from "../app/lib/image-sizes.ts";

test("a product card follows the columns of the grid it stands in", () => {
  assert.equal(CARD_SIZES, "(max-width: 480px) 100vw, (max-width: 900px) 50vw, (max-width: 1180px) 33vw, 25vw");
});

test("a tile spanning two columns is half the page, and the whole of a narrow one", () => {
  assert.equal(tileSizes("2x2"), "(max-width: 900px) 100vw, 50vw");
  assert.equal(tileSizes("2x1"), "(max-width: 900px) 100vw, 50vw");
});

test("a single-cell tile is a quarter of the page, and half of a narrow one", () => {
  assert.equal(tileSizes("1x1"), "(max-width: 900px) 50vw, 25vw");
});
