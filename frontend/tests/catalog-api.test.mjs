import assert from "node:assert/strict";
import { createServer } from "node:http";
import test from "node:test";

import { CatalogApi } from "../app/lib/catalog-api.ts";

const product = {
  id: "0a3e0fc0-793d-498f-b1cc-02111ea385d2",
  name: "Лира",
  slug: "lira",
  price_from: "18900",
  image_keys: [],
  description: "Зеркало для ванной.",
  attributes: [],
  variants: [],
};

test("the SSR client requests a product from its internal API base URL", async (t) => {
  const server = createServer((request, response) => {
    assert.equal(request.url, "/catalog/products/lira");
    response.setHeader("content-type", "application/json");
    response.end(JSON.stringify(product));
  });
  await new Promise((resolve) => server.listen(0, resolve));
  t.after(() => server.close());

  const address = server.address();
  if (address === null || typeof address === "string") {
    throw new Error("The local API server did not expose a TCP port");
  }
  const api = new CatalogApi(`http://127.0.0.1:${address.port}`);

  assert.deepEqual(await api.product("lira"), product);
});
