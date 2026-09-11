import assert from "node:assert/strict";
import test from "node:test";

import { coverImage, coverImageUrl, hasPhotographs, imageSrcSet, mediaUrl } from "../app/lib/media.ts";

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

test("a photograph offers the browser every copy the storage holds", () => {
  const image = { key: "a.jpg", variants: [{ key: "a-480w.webp", width: 480 }, { key: "a-960w.webp", width: 960 }] };

  assert.equal(imageSrcSet(image), "/media/a-480w.webp 480w, /media/a-960w.webp 960w");
});

test("a photograph without copies offers no candidates at all", () => {
  assert.equal(imageSrcSet({ key: "a.jpg", variants: [] }), undefined);
  assert.equal(imageSrcSet(undefined), undefined);
});

test("a card stands on the first photograph of the gallery", () => {
  const first = { key: "a.jpg", variants: [] };

  assert.equal(coverImage([first, { key: "b.jpg", variants: [] }]), first);
});
