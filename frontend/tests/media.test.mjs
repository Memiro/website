import assert from "node:assert/strict";
import test from "node:test";

import { coverImageUrl, hasPhotographs, mediaUrl } from "../app/lib/media.ts";

test("a stored key becomes a media address the edge serves", () => {
  assert.equal(mediaUrl("products/small/lira.webp"), "/media/products/small/lira.webp");
});

test("a card shows the first photograph of the product", () => {
  assert.equal(coverImageUrl(["products/small/a.webp", "products/small/b.webp"]), "/media/products/small/a.webp");
});

test("a product without photographs falls back to the studio placeholder", () => {
  assert.equal(coverImageUrl([]), "/img/placeholder.svg");
  assert.equal(hasPhotographs([]), false);
});
