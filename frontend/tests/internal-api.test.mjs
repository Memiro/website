import assert from "node:assert/strict";
import test from "node:test";

import { internalApiBaseUrl } from "../app/lib/internal-api.ts";

// A failing assert must not leave the variable behind for whatever runs next
// in this process.
function withAddress(configured, check) {
  const before = process.env.API_INTERNAL_URL;
  if (configured === undefined) {
    delete process.env.API_INTERNAL_URL;
  } else {
    process.env.API_INTERNAL_URL = configured;
  }
  try {
    check();
  } finally {
    if (before === undefined) {
      delete process.env.API_INTERNAL_URL;
    } else {
      process.env.API_INTERNAL_URL = before;
    }
  }
}

test("the contour's address for the API comes from the running process", () => {
  withAddress("http://api.test:9000", () => {
    assert.equal(internalApiBaseUrl(), "http://api.test:9000");
  });
});

test("a contour that names no address falls back to the one compose gives", () => {
  withAddress(undefined, () => {
    assert.equal(internalApiBaseUrl(), "http://api:8000");
  });
});

test("an empty variable is no address at all", () => {
  withAddress("   ", () => {
    assert.equal(internalApiBaseUrl(), "http://api:8000");
  });
});
