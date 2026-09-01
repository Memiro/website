import assert from "node:assert/strict";
import { createServer } from "node:http";
import test from "node:test";

import { ApiPayloadError, ApiResponseError, ApiUnreachableError, requestJson } from "../app/lib/http.ts";

/** @type {(value: unknown) => value is unknown} */
const isAnything = (value) => value !== undefined;

test("an HTML page from the proxy becomes a typed refusal instead of a parse error", async (t) => {
  const url = await serving(t, (_, response) => {
    response.statusCode = 502;
    response.setHeader("content-type", "text/html; charset=utf-8");
    response.end("<html><body>Bad Gateway</body></html>");
  });

  const failure = await rejection(requestJson({ url: new URL("/catalog/categories", url), isBody: isAnything }));

  assert.ok(failure instanceof ApiResponseError);
  assert.equal(failure.status, 502);
  assert.equal(failure.code, null);
});

test("a refusal in the API format carries its machine code", async (t) => {
  const url = await serving(t, (_, response) => {
    response.statusCode = 409;
    response.setHeader("content-type", "application/json");
    response.end(JSON.stringify({ code: "EMPTY_INQUIRY", message: "Заявка пуста", meta: {} }));
  });

  const failure = await rejection(requestJson({ url: new URL("/api/inquiries", url), isBody: isAnything }));

  assert.ok(failure instanceof ApiResponseError);
  assert.equal(failure.code, "EMPTY_INQUIRY");
});

test("an answer that does not match the contract is refused instead of trusted", async (t) => {
  const url = await serving(t, (_, response) => {
    response.setHeader("content-type", "application/json");
    response.end(JSON.stringify({ items: "not a list" }));
  });

  const failure = await rejection(
    requestJson({
      url: new URL("/catalog/categories", url),
      isBody: /** @type {(value: unknown) => value is unknown[]} */ ((value) => Array.isArray(value)),
    }),
  );

  assert.ok(failure instanceof ApiPayloadError);
});

test("a hanging API releases the page when the timeout expires", async (t) => {
  const url = await serving(t, () => {});

  const failure = await rejection(
    requestJson({ url: new URL("/catalog/categories", url), isBody: isAnything, timeoutMs: 50 }),
  );

  assert.ok(failure instanceof ApiUnreachableError);
});

test("a request with a body is posted as JSON", async (t) => {
  let received = { method: "", path: "", body: null, contentType: "" };
  const url = await serving(t, async (incoming, response) => {
    received = {
      method: incoming.method ?? "",
      path: incoming.url ?? "",
      body: JSON.parse(await readBody(incoming)),
      contentType: incoming.headers["content-type"] ?? "",
    };
    response.setHeader("content-type", "application/json");
    response.end(JSON.stringify({ verdict: "PRICED" }));
  });

  const answer = await requestJson({
    url: new URL("/api/calculate", url),
    post: { product_id: "mirror" },
    isBody: isAnything,
  });

  assert.deepEqual(received, {
    method: "POST",
    path: "/api/calculate",
    body: { product_id: "mirror" },
    contentType: "application/json",
  });
  assert.deepEqual(answer, { verdict: "PRICED" });
});

async function serving(t, handler) {
  const server = createServer(handler);
  await new Promise((resolve) => server.listen(0, () => resolve(undefined)));
  t.after(() => server.close());
  const address = server.address();
  if (address === null || typeof address === "string") {
    throw new Error("The local API server did not expose a TCP port");
  }
  return `http://127.0.0.1:${address.port}`;
}

async function rejection(promise) {
  try {
    await promise;
  } catch (error) {
    return error;
  }
  throw new Error("The request was expected to fail");
}

async function readBody(request) {
  const chunks = [];
  for await (const chunk of request) {
    chunks.push(chunk);
  }
  return Buffer.concat(chunks).toString();
}
