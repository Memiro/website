import assert from "node:assert/strict";
import { createServer } from "node:http";
import test from "node:test";

import { SubmitInquiryError, inquiryErrorMessage, submitInquiry } from "../app/islands/submit-inquiry.ts";

const request = {
  source: "SELECTION",
  name: "Анна",
  phone: "+79990000000",
  email: null,
  consent: true,
  comment: "",
  items: [],
};

test("the inquiry island submits its selection through the public inquiry route", async (t) => {
  let receivedMethod = "";
  let receivedPath = "";
  let receivedBody = null;
  const server = createServer(async (incoming, response) => {
    receivedMethod = incoming.method ?? "";
    receivedPath = incoming.url ?? "";
    receivedBody = JSON.parse(await readBody(incoming));
    response.setHeader("content-type", "application/json");
    response.end(JSON.stringify({ id: "24df5b9a-4d51-4f39-b4f2-5c94c2e3b8b2" }));
  });
  await new Promise((resolve) => server.listen(0, resolve));
  t.after(() => server.close());

  const address = server.address();
  if (address === null || typeof address === "string") {
    throw new Error("The local inquiry server did not expose a TCP port");
  }

  const response = await submitInquiry(request, `http://127.0.0.1:${address.port}`);

  assert.equal(receivedMethod, "POST");
  assert.equal(receivedPath, "/api/inquiries");
  assert.deepEqual(receivedBody, request);
  assert.deepEqual(response, {
    id: "24df5b9a-4d51-4f39-b4f2-5c94c2e3b8b2",
  });
});

test("the inquiry island translates a rejected consent into customer copy", () => {
  assert.equal(inquiryErrorMessage(new SubmitInquiryError("CONSENT_REQUIRED")), "Подтвердите согласие на обработку персональных данных.");
  assert.equal(inquiryErrorMessage(new SubmitInquiryError("INQUIRY_SOURCE_NOT_ACCEPTED")), "Эту форму заявки больше нельзя отправить. Обновите страницу и попробуйте снова.");
  assert.equal(inquiryErrorMessage(new SubmitInquiryError("INVALID_INQUIRY_CONTENTS")), "Состав заявки изменился. Обновите страницу и попробуйте снова.");
});

async function readBody(request) {
  const chunks = [];
  for await (const chunk of request) {
    chunks.push(chunk);
  }
  return Buffer.concat(chunks).toString();
}
