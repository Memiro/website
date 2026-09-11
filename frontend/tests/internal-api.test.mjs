import assert from "node:assert/strict";
import test from "node:test";

import { internalApiBaseUrl } from "../app/lib/internal-api.ts";

test("the contour's address for the API comes from the running process", () => {
  process.env.API_INTERNAL_URL = "http://api.test:9000";

  assert.equal(internalApiBaseUrl(), "http://api.test:9000");

  delete process.env.API_INTERNAL_URL;
});

test("a contour that names no address falls back to the one compose gives", () => {
  delete process.env.API_INTERNAL_URL;

  assert.equal(internalApiBaseUrl(), "http://api:8000");
});

test("an empty variable is no address at all", () => {
  process.env.API_INTERNAL_URL = "   ";

  assert.equal(internalApiBaseUrl(), "http://api:8000");

  delete process.env.API_INTERNAL_URL;
});
