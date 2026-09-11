import assert from "node:assert/strict";
import test from "node:test";

import {
  freeFormInquiry,
  canAddCalculatorConfiguration,
  canShowInquiryEditor,
  addInquiryItem,
  hasUnavailableItem,
  inquiryItemFromCalculator,
  isInquiryPreview,
  previewRequest,
  previewedPricePresentation,
  removeInquiryItem,
  loadInquiryItems,
  selectionInquiry,
  specificationLine,
} from "../app/lib/inquiry-state.ts";

test("a beyond-limits calculator configuration becomes a selection wish without browser pricing", () => {
  const item = inquiryItemFromCalculator(
    {
      id: "mirror",
      updated_at: "2026-09-01T10:00:00Z",
      name: "Зеркало Loft",
      slug: "loft",
      category_slug: "zerkala",
      category_name: "Зеркала",
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

test("the preview asks with the very positions the submission will send", () => {
  const item = {
    productId: "mirror",
    productName: "Зеркало Loft",
    widthMm: 800,
    heightMm: 600,
    selections: [{ attributeId: "blade", valueId: "graphite", quantity: null }],
    wish: "Тёплый свет",
    isWish: false,
  };

  const request = previewRequest([item]);

  assert.deepEqual(request, {
    items: [
      {
        product_id: "mirror",
        width_mm: 800,
        height_mm: 600,
        selections: [{ attribute_id: "blade", value_id: "graphite", quantity: null }],
        wish: "Тёплый свет",
      },
    ],
  });
  assert.deepEqual(request.items, selectionInquiry([item], { name: "Анна", phone: "+79990000000", email: "", consent: true }).items);
});

test("a preview answer is read only when every position matches the contract", () => {
  const priced = {
    product_id: "mirror",
    is_available: true,
    product_name: "Зеркало Loft",
    price_from: "8820.00",
    verdict: "PRICED",
    price: "10020.00",
    configuration: {
      width_mm: 800,
      height_mm: 600,
      values: [{ attribute_name: "Тип полотна", value_name: "Графит", quantity: null }],
    },
    wish: "",
  };
  const gone = {
    product_id: "old",
    is_available: false,
    product_name: null,
    price_from: null,
    verdict: null,
    price: null,
    configuration: null,
    wish: "Для холла",
  };

  assert.equal(isInquiryPreview({ items: [priced, gone] }), true);
  assert.equal(isInquiryPreview({ items: [{ ...priced, configuration: { width_mm: "800" } }] }), false);
  assert.equal(isInquiryPreview({ items: [{ ...priced, verdict: "FREE" }] }), false);
  assert.equal(isInquiryPreview({ items: "none" }), false);
  assert.equal(isInquiryPreview(null), false);
});

test("a selection with a product taken off the storefront cannot be sent until it is removed", () => {
  /** @type {import("../app/lib/inquiry-state.ts").PreviewedItem} */
  const available = { product_id: "a", is_available: true, product_name: "A", price_from: null, verdict: "PRICED", price: "1000", configuration: null, wish: "" };
  /** @type {import("../app/lib/inquiry-state.ts").PreviewedItem} */
  const gone = { ...available, product_id: "b", is_available: false, product_name: null, verdict: null, price: null };

  assert.equal(hasUnavailableItem([available]), false);
  assert.equal(hasUnavailableItem([available, gone]), true);
});

test("a previewed position is explained in the words of the product card, without deltas", () => {
  const base = { product_id: "a", is_available: true, product_name: "A", price_from: null, configuration: null, wish: "" };

  assert.deepEqual(previewedPricePresentation({ ...base, verdict: "PRICED", price: "10020.00" }), {
    kind: "priced",
    total: "10020.00",
    message: null,
    deltas: [],
  });
  assert.equal(previewedPricePresentation({ ...base, verdict: "HIDDEN", price: null })?.message, "Стоимость этой конфигурации уточнит менеджер.");
  assert.equal(previewedPricePresentation({ ...base, verdict: "BEYOND_LIMITS", price: null })?.kind, "wish");
  assert.equal(previewedPricePresentation({ ...base, verdict: "SELECTION_NOT_PRICEABLE", price: null })?.message, "Цену такого сочетания назовёт менеджер.");
  assert.equal(previewedPricePresentation({ ...base, is_available: false, verdict: null, price: null }), null);
});

test("a value of the specification reads as attribute and value, a count in whole units", () => {
  assert.equal(specificationLine({ attribute_name: "Рама", value_name: "Без рамы", quantity: null }), "Рама: Без рамы");
  assert.equal(specificationLine({ attribute_name: "Вырезы", value_name: null, quantity: "2.5000" }), "Вырезы: 2.5");
  assert.equal(specificationLine({ attribute_name: "Вырезы", value_name: null, quantity: "1.0000" }), "Вырезы: 1");
});
