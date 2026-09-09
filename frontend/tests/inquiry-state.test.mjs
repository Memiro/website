import assert from "node:assert/strict";
import test from "node:test";

import {
  freeFormInquiry,
  canAddCalculatorConfiguration,
  canShowInquiryEditor,
  addInquiryItem,
  inquiryItemFromCalculator,
  removeInquiryItem,
  loadInquiryItems,
  selectionInquiry,
} from "../app/lib/inquiry-state.ts";

test("a beyond-limits calculator configuration becomes a selection wish without browser pricing", () => {
  const item = inquiryItemFromCalculator(
    {
      id: "mirror",
      name: "Зеркало Loft",
      slug: "loft",
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

test("a browser that refuses to remember the basket still accepts the configuration", () => {
  const storage = new RefusingStorage();
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

  assert.deepEqual(items, [item]);
});

test("removing a position drops it from the browser storage too", () => {
  const storage = new MapStorage();
  const first = { productId: "first", productName: "Первое", widthMm: 800, heightMm: 600, selections: [], wish: "", isWish: false };
  const second = { productId: "second", productName: "Второе", widthMm: 900, heightMm: 700, selections: [], wish: "", isWish: false };
  const items = addInquiryItem(storage, addInquiryItem(storage, [], first), second);

  const kept = removeInquiryItem(storage, items, 0);

  assert.deepEqual(kept, [second]);
  assert.deepEqual(loadInquiryItems(storage), [second]);
});

test("a broken basket in storage is read as an empty basket", () => {
  const storage = new MapStorage();
  storage.setItem("memiro.inquiry-items", "{not json");

  assert.deepEqual(loadInquiryItems(storage), []);
});

class RefusingStorage {
  getItem() {
    return null;
  }

  setItem() {
    throw new Error("The browser refuses to store anything in this mode");
  }
}

class MapStorage {
  #values = new Map();

  getItem(key) {
    return this.#values.get(key) ?? null;
  }

  setItem(key, value) {
    this.#values.set(key, value);
  }
}

test("a selection inquiry carries the comment typed next to the contacts", () => {
  const item = { productId: "mirror", productName: "Зеркало Loft", widthMm: 600, heightMm: 800, selections: [], wish: "", isWish: false };

  const request = selectionInquiry([item], { name: "Анна", phone: "+79990000000", email: "", consent: true }, "Нужно к пятнице");

  assert.equal(request.comment, "Нужно к пятнице");
});

test("a free-form inquiry carries a comment and no items", () => {
  const request = freeFormInquiry({ name: "Аня", phone: "+79990000000", email: "", consent: true }, "Нужна арка");

  assert.equal(request.source, "FREE_FORM");
  assert.equal(request.comment, "Нужна арка");
  assert.equal(request.email, null);
  assert.deepEqual(request.items, []);
});

test("a configuration the calculator could not price is still a position of the inquiry", () => {
  assert.equal(canShowInquiryEditor("unpriced"), true);
  assert.equal(canAddCalculatorConfiguration("unpriced", ""), true);
});

test("a hidden price does not take the position away either", () => {
  assert.equal(canShowInquiryEditor("hidden"), true);
  assert.equal(canAddCalculatorConfiguration("hidden", ""), true);
});

test("a product outside the calculable set has no configuration to add", () => {
  assert.equal(canShowInquiryEditor("unavailable"), false);
  assert.equal(canAddCalculatorConfiguration("unavailable", ""), false);
});
