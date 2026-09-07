import assert from "node:assert/strict";
import { createServer } from "node:http";
import test from "node:test";

import { applyLabel, countProducts } from "../app/islands/filters.ts";

test("the filter sidebar counts the narrowing the visitor has not applied yet", async (t) => {
  let receivedPath = "";
  const server = createServer((incoming, response) => {
    receivedPath = incoming.url ?? "";
    response.setHeader("content-type", "application/json");
    response.end(JSON.stringify({
      items: [],
      total: 3,
      page: 1,
      pages: 1,
      sort: "name",
      groups: [],
      price: null,
    }));
  });
  await new Promise((resolve) => server.listen(0, () => resolve(undefined)));
  t.after(() => server.close());

  const address = server.address();
  if (address === null || typeof address === "string") {
    throw new Error("The local catalogue server did not expose a TCP port");
  }

  const total = await countProducts("zerkala", "value=a&value=b", `http://127.0.0.1:${address.port}`);

  assert.equal(total, 3);
  assert.equal(receivedPath, "/api/catalog/categories/zerkala/products?value=a&value=b");
});

test("the apply button names the count it knows and drops it while it does not", () => {
  assert.equal(applyLabel(3), "Показать 3 товара");
  assert.equal(applyLabel(1), "Показать 1 товар");
  assert.equal(applyLabel(0), "Показать 0 товаров");
  assert.equal(applyLabel(null), "Показать");
});
