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
  attributes: [
    { id: "frame", name: "Рама", kind: "select", values: [{ id: "black", name: "Чёрная", quantity: null }] },
    { id: "cut-outs", name: "Вырезы", kind: "number", values: [{ id: "cut-out", name: "Вырез", quantity: null }] },
  ],
  variants: [],
};

const cardWithoutAttributeKind = { ...product, attributes: [{ id: "frame", name: "Рама", values: [] }] };

const categories = { items: [{ name: "Зеркала", slug: "mirrors" }], total: 1, page: 1 };

const categoryProducts = {
  items: [{ name: "Лира", slug: "lira", price_from: "18900", image_keys: [] }],
  total: 1,
  page: 1,
};

/** Serve the given handler on a loopback port and hand the client that speaks to it. */
async function withApi(t, handler) {
  const server = createServer((request, response) => {
    response.setHeader("content-type", "application/json");
    handler(request, response);
  });
  await new Promise((resolve) => server.listen(0, () => resolve(undefined)));
  t.after(() => server.close());

  const address = server.address();
  if (address === null || typeof address === "string") {
    throw new Error("The local API server did not expose a TCP port");
  }
  return new CatalogApi(`http://127.0.0.1:${address.port}`);
}

test("the SSR client reads catalogue lists as the {items, total, page} envelope", async (t) => {
  const bodies = { "/catalog/categories": categories, "/catalog/categories/mirrors/products": categoryProducts };
  const api = await withApi(t, (request, response) => response.end(JSON.stringify(bodies[request.url])));

  assert.deepEqual(await api.categories(), categories);
  assert.deepEqual(await api.categoryProducts("mirrors"), categoryProducts);
});

test("the SSR client requests a product from its internal API base URL", async (t) => {
  const api = await withApi(t, (request, response) => {
    assert.equal(request.url, "/catalog/products/lira");
    response.end(JSON.stringify(product));
  });

  assert.deepEqual(await api.product("lira"), product);
});

test("the SSR client refuses a product card whose attribute does not say how it is configured", async (t) => {
  const api = await withApi(t, (_, response) => response.end(JSON.stringify(cardWithoutAttributeKind)));

  await assert.rejects(api.product("lira"));
});
