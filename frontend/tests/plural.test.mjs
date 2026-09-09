import assert from "node:assert/strict";
import test from "node:test";

import { categoryPlural, productPlural } from "../app/lib/plural.ts";

test("a single product is counted in the singular", () => {
  assert.equal(productPlural(1), "товар");
});

test("two to four products take the genitive singular", () => {
  assert.equal(productPlural(3), "товара");
});

test("the teens are counted in the plural despite their last digit", () => {
  assert.equal(productPlural(11), "товаров");
  assert.equal(productPlural(112), "товаров");
});

test("an empty category is counted in the plural", () => {
  assert.equal(productPlural(0), "товаров");
});

test("a single category is counted in the singular", () => {
  assert.equal(categoryPlural(1), "категория");
});

test("two to four categories take the genitive singular", () => {
  assert.equal(categoryPlural(4), "категории");
});

test("five categories and the teens are counted in the plural", () => {
  assert.equal(categoryPlural(6), "категорий");
  assert.equal(categoryPlural(11), "категорий");
});
