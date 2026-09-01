import assert from "node:assert/strict";
import { createServer } from "node:http";
import test from "node:test";

import { ApiPayloadError } from "../app/lib/http.ts";
import { calculatePrice } from "../app/islands/calculate-price.ts";

test("the calculator sends its configuration through the public pricing route", async (t) => {
  const server = createServer((request, response) => {
    assert.equal(request.method, "POST");
    assert.equal(request.url, "/api/calculate");
    response.setHeader("content-type", "application/json");
    response.end(JSON.stringify({ verdict: "PRICED", total: "8900", selection_deltas: [] }));
  });
  await new Promise((resolve) => server.listen(0, () => resolve(undefined)));
  t.after(() => server.close());

  const address = server.address();
  if (address === null || typeof address === "string") {
    throw new Error("The local pricing server did not expose a TCP port");
  }

  assert.deepEqual(
    await calculatePrice(
      { product_id: "mirror", width_mm: 800, height_mm: 600, selections: [] },
      `http://127.0.0.1:${address.port}`,
    ),
    { verdict: "PRICED", total: "8900", selection_deltas: [] },
  );
});

test("an answer that is not a price is refused instead of shown as one", async (t) => {
  const server = createServer((_, response) => {
    response.setHeader("content-type", "application/json");
    response.end(JSON.stringify({ verdict: "MAYBE", total: 8900 }));
  });
  await new Promise((resolve) => server.listen(0, () => resolve(undefined)));
  t.after(() => server.close());

  const address = server.address();
  if (address === null || typeof address === "string") {
    throw new Error("The local pricing server did not expose a TCP port");
  }

  await assert.rejects(
    calculatePrice(
      { product_id: "mirror", width_mm: 800, height_mm: 600, selections: [] },
      `http://127.0.0.1:${address.port}`,
    ),
    ApiPayloadError,
  );
});
