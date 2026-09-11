import assert from "node:assert/strict";
import test from "node:test";

import { hasPhotographs, imageSrcSet, mediaUrl, photographUrl } from "../app/lib/media.ts";

test("a stored key becomes a media address the edge serves", () => {
  assert.equal(mediaUrl("products/small/lira.webp"), "/media/products/small/lira.webp");
});

test("a product without photographs is known to have none", () => {
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

test("a photograph is addressed by its key, and its absence by the placeholder", () => {
  assert.equal(photographUrl({ key: "a.jpg", variants: [] }), "/media/a.jpg");
  assert.equal(photographUrl(null), "/img/placeholder.svg");
  assert.equal(photographUrl(undefined), "/img/placeholder.svg");
});
