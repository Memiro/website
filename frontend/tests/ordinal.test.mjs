import assert from "node:assert/strict";
import test from "node:test";

import { ordinal } from "../app/lib/ordinal.ts";

test("a single-digit position is padded to two digits", () => {
  assert.equal(ordinal(1), "01");
});

test("a two-digit position is left as it is", () => {
  assert.equal(ordinal(12), "12");
});
