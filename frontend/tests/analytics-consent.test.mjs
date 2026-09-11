import assert from "node:assert/strict";
import test from "node:test";

import { ACCEPTED, analyticsGate, DECLINED, validCounterId } from "../app/lib/analytics-consent.ts";

test("a visitor who has not answered yet is asked", () => {
  assert.equal(analyticsGate("12345", undefined), "banner");
});

test("the counter arrives only for a visitor who accepted", () => {
  assert.equal(analyticsGate("12345", ACCEPTED), "counter");
});

test("a visitor who declined gets neither the counter nor the banner again", () => {
  assert.equal(analyticsGate("12345", DECLINED), "silence");
});

test("a made-up answer in the cookie asks again instead of counting", () => {
  assert.equal(analyticsGate("12345", "true"), "banner");
});

test("a contour without a counter asks about nothing", () => {
  assert.equal(analyticsGate("", undefined), "silence");
  assert.equal(analyticsGate("", ACCEPTED), "silence");
});

test("the counter number is read from the contour and trimmed", () => {
  assert.equal(validCounterId(" 12345 "), "12345");
});

test("anything that is not a counter number is no counter at all", () => {
  assert.equal(validCounterId(undefined), "");
  assert.equal(validCounterId(""), "");
  assert.equal(validCounterId("12345; alert(1)"), "");
});
