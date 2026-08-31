import assert from "node:assert/strict";
import test from "node:test";

import { Calculator, calculatorStateForVariant, initialCalculatorState, pricePresentation, toCalculateRequest } from "../app/lib/calculator-state.ts";

const MIRROR = {
  id: "mirror",
  name: "Зеркало Loft",
  slug: "loft",
  description: "",
  price_from: null,
  image_keys: [],
  attributes: [
    { id: "frame", name: "Рама", values: [{ id: "black", name: "Чёрная", quantity: null }, { id: "white", name: "Белая", quantity: null }] },
    { id: "shelves", name: "Полки", values: [] },
  ],
  variants: [
    { width_mm: 800, height_mm: 600, price: "8900", overrides: [{ attribute_id: "frame", value_id: "black", quantity: null }] },
    { width_mm: 1000, height_mm: 700, price: "10900", overrides: [] },
  ],
};

function pricedAt(total) {
  return { verdict: "PRICED", total, selection_deltas: [] };
}

function recordingPricing(answer = pricedAt("9000")) {
  const requests = [];
  return {
    requests,
    calculate: (request) => {
      requests.push(request);
      return Promise.resolve(answer);
    },
  };
}

/** Answer every call in the order the test releases it, not in the order it arrived. */
function queuedPricing() {
  const requests = [];
  const releases = [];
  const calculate = (request) => {
    requests.push(request);
    return new Promise((resolve, reject) => releases.push({ resolve, reject }));
  };
  return { requests, releases, calculate };
}

test("an answer to a superseded configuration never replaces the answer to the newest one", async () => {
  const pricing = queuedPricing();
  const calculator = new Calculator(MIRROR, pricing.calculate);

  const first = calculator.setWidth("900");
  const second = calculator.setWidth("1200");
  pricing.releases[1].resolve(pricedAt("12000"));
  await second;
  pricing.releases[0].resolve(pricedAt("9000"));
  await first;

  assert.equal(calculator.request.status, "done");
  assert.equal(calculator.request.price.total, "12000");
  assert.deepEqual(pricing.requests.map((request) => request.width_mm), [900, 1200]);
});

test("a superseded failure leaves the newest request loading instead of clearing it", async () => {
  const pricing = queuedPricing();
  const calculator = new Calculator(MIRROR, pricing.calculate);

  const first = calculator.setWidth("900");
  const second = calculator.setWidth("1200");
  pricing.releases[0].reject(new Error("network"));
  await first;

  assert.deepEqual(calculator.request, { status: "loading" });
  pricing.releases[1].resolve(pricedAt("12000"));
  await second;
  assert.equal(calculator.request.status, "done");
});

test("a failed answer to the newest configuration becomes an error state", async () => {
  const pricing = queuedPricing();
  const calculator = new Calculator(MIRROR, pricing.calculate);

  const pending = calculator.setWidth("900");
  pricing.releases[0].reject(new Error("network"));
  await pending;

  assert.deepEqual(calculator.request, { status: "error" });
});

test("an empty size is highlighted in the form instead of being sent", async () => {
  const pricing = queuedPricing();
  const calculator = new Calculator(MIRROR, pricing.calculate);

  await calculator.setWidth("");

  assert.deepEqual(calculator.request, { status: "invalid", fields: ["widthMm"] });
  assert.equal(calculator.isInvalid("widthMm"), true);
  assert.deepEqual(pricing.requests, []);
});

test("an impossible size is highlighted in the form instead of being sent", async () => {
  const pricing = queuedPricing();
  const calculator = new Calculator(MIRROR, pricing.calculate);

  await calculator.setHeight("0");

  assert.deepEqual(calculator.request, { status: "invalid", fields: ["heightMm"] });
  assert.deepEqual(pricing.requests, []);
});

test("a quantity that is not a number is highlighted under its own attribute", async () => {
  const pricing = queuedPricing();
  const calculator = new Calculator(MIRROR, pricing.calculate);

  await calculator.setQuantity("shelves", "две");

  assert.deepEqual(calculator.request, { status: "invalid", fields: ["shelves"] });
  assert.equal(calculator.isInvalid("shelves"), true);
  assert.deepEqual(pricing.requests, []);
});

test("clearing a quantity drops the choice instead of sending an empty one", async () => {
  const pricing = recordingPricing();
  const calculator = new Calculator(MIRROR, pricing.calculate);

  await calculator.setQuantity("shelves", "2");
  await calculator.setQuantity("shelves", "");

  assert.equal(calculator.chosenQuantity("shelves"), "");
  assert.deepEqual(pricing.requests[1].selections, [{ attribute_id: "frame", value_id: "black", quantity: null }]);
});

test("an invalid configuration cancels the answer to the request it superseded", async () => {
  const pricing = queuedPricing();
  const calculator = new Calculator(MIRROR, pricing.calculate);

  const pending = calculator.setWidth("900");
  await calculator.setWidth("");
  pricing.releases[0].resolve(pricedAt("9000"));
  await pending;

  assert.deepEqual(calculator.request, { status: "invalid", fields: ["widthMm"] });
});

test("an attribute the variant does not override shows no choice and sends none", async () => {
  const pricing = recordingPricing();
  const calculator = new Calculator(MIRROR, pricing.calculate);

  await calculator.chooseVariant(1);

  assert.equal(calculator.chosenValue("frame"), "");
  assert.deepEqual(pricing.requests[0].selections, []);
});

test("the value the customer sees chosen is the value that is sent", async () => {
  const pricing = recordingPricing();
  const calculator = new Calculator(MIRROR, pricing.calculate);

  await calculator.chooseValue("frame", "white");

  assert.equal(calculator.chosenValue("frame"), "white");
  assert.deepEqual(pricing.requests[0].selections, [{ attribute_id: "frame", value_id: "white", quantity: null }]);
});

test("clearing a value returns the attribute to the value the product declares", async () => {
  const pricing = recordingPricing();
  const calculator = new Calculator(MIRROR, pricing.calculate);

  await calculator.chooseValue("frame", "");

  assert.equal(calculator.chosenValue("frame"), "");
  assert.deepEqual(pricing.requests[0].selections, []);
});

test("the variant select names the variant the configuration actually matches", async () => {
  const pricing = recordingPricing();
  const calculator = new Calculator(MIRROR, pricing.calculate);

  assert.equal(calculator.variantIndex, 0);
  await calculator.chooseVariant(1);
  assert.equal(calculator.variantIndex, 1);
});

test("choosing another material leaves the ready size the customer picked", async () => {
  const pricing = recordingPricing();
  const calculator = new Calculator(MIRROR, pricing.calculate);

  await calculator.chooseValue("frame", "white");

  assert.equal(calculator.variantIndex, 0);
});

test("a variant the product does not have leaves the configuration untouched", async () => {
  const pricing = recordingPricing();
  const calculator = new Calculator(MIRROR, pricing.calculate);

  await calculator.chooseVariant(7);

  assert.equal(calculator.widthText, "800");
  assert.deepEqual(pricing.requests, []);
});

test("a size the customer typed himself matches no variant", async () => {
  const pricing = recordingPricing();
  const calculator = new Calculator(MIRROR, pricing.calculate);

  await calculator.setWidth("930");

  assert.equal(calculator.variantIndex, null);
});

test("the configuration behind a price is the one the customer can put in the inquiry", async () => {
  const pricing = queuedPricing();
  const calculator = new Calculator(MIRROR, pricing.calculate);

  const pending = calculator.setWidth("900");
  pricing.releases[0].resolve(pricedAt("9000"));
  await pending;

  assert.deepEqual(calculator.priced, {
    widthMm: 900,
    heightMm: 600,
    selections: [{ attributeId: "frame", valueId: "black", quantity: null }],
  });
});

test("a hidden price tells the customer a manager will name it", () => {
  assert.deepEqual(
    pricePresentation({ verdict: "HIDDEN", total: null, selection_deltas: [] }),
    {
      kind: "hidden",
      total: null,
      message: "Стоимость этой конфигурации уточнит менеджер.",
      deltas: [],
    },
  );
});

test("a configuration that cannot be priced says so instead of showing a price", () => {
  assert.deepEqual(
    pricePresentation({ verdict: "NOT_PRICEABLE", total: null, selection_deltas: [] }),
    {
      kind: "unavailable",
      total: null,
      message: "Эту конфигурацию пока нельзя рассчитать.",
      deltas: [],
    },
  );
});

test("the first product variant opens the calculator with its size and overrides", () => {
  const state = initialCalculatorState({
    id: "mirror",
    attributes: [],
    variants: [
      {
        width_mm: 800,
        height_mm: 600,
        price: "8900",
        overrides: [{ attribute_id: "blade", value_id: "graphite", quantity: null }],
      },
    ],
  });

  assert.deepEqual(state, {
    widthMm: 800,
    heightMm: 600,
    selections: [{ attributeId: "blade", valueId: "graphite", quantity: null }],
  });
});

test("a beyond-limits result invites the customer to leave a wish without a price", () => {
  assert.deepEqual(
    pricePresentation({ verdict: "BEYOND_LIMITS", total: null, selection_deltas: [] }),
    {
      kind: "wish",
      total: null,
      message: "Этот размер изготовим по индивидуальному пожеланию.",
      deltas: [],
    },
  );
});

test("a priced result keeps every server-calculated selection delta", () => {
  assert.deepEqual(
    pricePresentation({
      verdict: "PRICED",
      total: "12500",
      selection_deltas: [{ attribute_id: "frame", value_id: "black", delta: "1200" }],
    }),
    {
      kind: "priced",
      total: "12500",
      message: null,
      deltas: [{ attributeId: "frame", valueId: "black", amount: "1200" }],
    },
  );
});

test("choosing a product variant replaces the calculator configuration", () => {
  const product = {
    id: "mirror",
    attributes: [],
    variants: [
      { width_mm: 800, height_mm: 600, price: "8900", overrides: [] },
      { width_mm: 1000, height_mm: 700, price: "10900", overrides: [{ attribute_id: "frame", value_id: "black", quantity: null }] },
    ],
  };

  assert.deepEqual(calculatorStateForVariant(product, 1), {
    widthMm: 1000,
    heightMm: 700,
    selections: [{ attributeId: "frame", valueId: "black", quantity: null }],
  });
});

test("the calculator sends only its current configuration to the pricing endpoint", () => {
  assert.deepEqual(
    toCalculateRequest("mirror", {
      widthMm: 900,
      heightMm: 700,
      selections: [{ attributeId: "blade", valueId: "graphite", quantity: null }],
    }),
    {
      product_id: "mirror",
      width_mm: 900,
      height_mm: 700,
      selections: [{ attribute_id: "blade", value_id: "graphite", quantity: null }],
    },
  );
});
