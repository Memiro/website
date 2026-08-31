import assert from "node:assert/strict";
import test from "node:test";

import { initialCalculatorState, pricePresentation } from "../src/lib/calculator-state.ts";

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
    },
  );
});
