import assert from "node:assert/strict";
import test from "node:test";

import { calculatorStateForVariant, initialCalculatorState, pricePresentation, toCalculateRequest } from "../app/lib/calculator-state.ts";

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
