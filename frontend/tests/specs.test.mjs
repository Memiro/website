import assert from "node:assert/strict";
import test from "node:test";

import { productSpecs } from "../app/lib/specs.ts";

/** @type {import("../app/lib/catalog-api.ts").ProductAttribute} */
const BLADE = {
  id: "blade",
  name: "Тип полотна",
  kind: "select",
  declared_value_id: "graphite",
  values: [{ id: "silver", name: "Серебро", quantity: null }, { id: "graphite", name: "Графит", quantity: null }],
};

test("a characteristic names the row the product itself is made of", () => {
  assert.deepEqual(productSpecs([BLADE]), [{ name: "Тип полотна", value: "Графит" }]);
});

test("a numeric attribute is described by the count the product declared", () => {
  /** @type {import("../app/lib/catalog-api.ts").ProductAttribute} */
  const cutouts = {
    id: "cutouts",
    name: "Вырезы",
    kind: "number",
    declared_value_id: null,
    values: [{ id: null, name: "Вырез", quantity: "2.0000" }],
  };

  assert.deepEqual(productSpecs([cutouts]), [{ name: "Вырезы", value: "2 шт." }]);
});

test("an attribute the product never declared is not a characteristic of it", () => {
  const undeclared = { ...BLADE, declared_value_id: null };

  assert.deepEqual(productSpecs([undeclared]), []);
});
