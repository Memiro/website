import assert from "node:assert/strict";
import test from "node:test";

import { tileSpan } from "../app/lib/tiles.ts";

test("the first tile of a bento takes the two-by-two cell", () => {
  assert.equal(tileSpan(0), "2x2");
});

test("the second and third tiles sit as single cells beside it", () => {
  assert.equal(tileSpan(1), "1x1");
  assert.equal(tileSpan(2), "1x1");
});

test("the fourth to sixth tiles stretch across two columns", () => {
  assert.equal(tileSpan(3), "2x1");
  assert.equal(tileSpan(4), "2x1");
  assert.equal(tileSpan(5), "2x1");
});

test("a seventh tile starts the pattern over", () => {
  assert.equal(tileSpan(6), "2x2");
  assert.equal(tileSpan(7), "1x1");
});
