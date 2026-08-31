import assert from "node:assert/strict";
import test from "node:test";

import {
  canAddCalculatorConfiguration,
  canShowInquiryEditor,
  addInquiryItem,
  inquiryItemFromCalculator,
  loadInquiryItems,
  selectionInquiry,
} from "../app/lib/inquiry-state.ts";

test("a beyond-limits calculator configuration becomes a selection wish without browser pricing", () => {
  const item = inquiryItemFromCalculator(
    {
      id: "mirror",
      name: "Зеркало Loft",
      attributes: [],
      variants: [],
      description: "",
      price_from: null,
      image_keys: [],
    },
    {
      widthMm: 3200,
      heightMm: 2400,
      selections: [{ attributeId: "frame", valueId: "black", quantity: null }],
    },
    "wish",
    "Изготовить для холла",
  );

  assert.deepEqual(item, {
    productId: "mirror",
    productName: "Зеркало Loft",
    widthMm: 3200,
    heightMm: 2400,
    selections: [{ attributeId: "frame", valueId: "black", quantity: null }],
    wish: "Изготовить для холла",
    isWish: true,
  });

  assert.deepEqual(selectionInquiry([item], { name: "Анна", phone: "+79990000000", email: "anna@example.com", consent: true }), {
    source: "SELECTION",
    name: "Анна",
    phone: "+79990000000",
    email: "anna@example.com",
    consent: true,
    comment: "",
    items: [
      {
        product_id: "mirror",
        width_mm: 3200,
        height_mm: 2400,
        selections: [{ attribute_id: "frame", value_id: "black", quantity: null }],
        wish: "Изготовить для холла",
      },
    ],
  });
});

test("a beyond-limits configuration needs a personal wish before it enters the inquiry", () => {
  assert.equal(canShowInquiryEditor("wish"), true);
  assert.equal(canAddCalculatorConfiguration("wish", ""), false);
  assert.equal(canAddCalculatorConfiguration("wish", "Нужен размер для холла"), true);
  assert.equal(canAddCalculatorConfiguration("priced", ""), true);
});

test("the inquiry basket keeps configurations while the customer opens another product", () => {
  const storage = new MapStorage();
  const item = {
    productId: "first-mirror",
    productName: "Зеркало Loft",
    widthMm: 800,
    heightMm: 600,
    selections: [],
    wish: "",
    isWish: false,
  };

  const items = addInquiryItem(storage, [], item);

  assert.deepEqual(loadInquiryItems(storage), items);
});

class MapStorage {
  #values = new Map();

  getItem(key) {
    return this.#values.get(key) ?? null;
  }

  setItem(key, value) {
    this.#values.set(key, value);
  }
}
