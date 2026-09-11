import assert from "node:assert/strict";
import test from "node:test";

import { analyticsGate, counterId } from "../app/lib/analytics-consent.ts";

test("a visitor who has not answered yet is asked", () => {
  assert.equal(analyticsGate("12345", undefined), "banner");
});

test("the counter arrives only for a visitor who accepted", () => {
  assert.equal(analyticsGate("12345", "yes"), "counter");
});

test("a visitor who declined gets neither the counter nor the banner again", () => {
  assert.equal(analyticsGate("12345", "no"), "silence");
});

test("a made-up answer in the cookie asks again instead of counting", () => {
  assert.equal(analyticsGate("12345", "true"), "banner");
});

test("a contour without a counter asks about nothing", () => {
  assert.equal(analyticsGate("", undefined), "silence");
  assert.equal(analyticsGate("", "yes"), "silence");
});

test("the counter number is read from the contour and trimmed", () => {
  assert.equal(counterId(" 12345 "), "12345");
});

test("anything that is not a counter number is no counter at all", () => {
  assert.equal(counterId(undefined), "");
  assert.equal(counterId(""), "");
  assert.equal(counterId("12345; alert(1)"), "");
});
