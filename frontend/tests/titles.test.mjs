import assert from "node:assert/strict";
import test from "node:test";

import { listingDescription, listingTitle, pagedTitle, productDescription, productTitle } from "../app/lib/titles.ts";

const NBSP = " ";

test("a bare Latin name is introduced as a mirror", () => {
  assert.equal(productTitle("Aura"), "Зеркало Aura на заказ в Санкт-Петербурге — Memiro");
});

test("a descriptive Russian name already says what it is and is not doubled", () => {
  assert.equal(productTitle("Зеркало в раме Falsie"), "Зеркало в раме Falsie на заказ в Санкт-Петербурге — Memiro");
  assert.equal(productTitle("Трельяж Ternion"), "Трельяж Ternion на заказ в Санкт-Петербурге — Memiro");
});

test("a priced product describes itself with its price and the first sentence of its copy", () => {
  assert.equal(
    productDescription("Aura", "18900.00", "Круглое зеркало с контурной подсветкой. Рама из алюминия, три цвета."),
    `Зеркало Aura на заказ от 18${NBSP}900 ₽. Круглое зеркало с контурной подсветкой. Изготовление, доставка и монтаж в Санкт-Петербурге.`,
  );
});

test("a product without a price keeps the sentence about the price out", () => {
  assert.equal(
    productDescription("Aura", null, "Круглое зеркало с контурной подсветкой. Рама из алюминия."),
    "Круглое зеркало с контурной подсветкой. Изготовление, доставка и монтаж в Санкт-Петербурге.",
  );
});

test("a copy of one sentence is taken whole, and a period is added when the owner left it out", () => {
  assert.equal(
    productDescription("Aura", null, "Зеркало с подсветкой 3000 K"),
    "Зеркало с подсветкой 3000 K. Изготовление, доставка и монтаж в Санкт-Петербурге.",
  );
});

test("a decimal inside the copy does not end its first sentence", () => {
  assert.equal(
    productDescription("Aura", null, "Толщина полотна 4.5 мм. Кромка полированная."),
    "Толщина полотна 4.5 мм. Изготовление, доставка и монтаж в Санкт-Петербурге.",
  );
});

test("a listing is titled by its category and the city", () => {
  assert.equal(listingTitle("Зеркала", 1), "Зеркала на заказ в Санкт-Петербурге — Memiro");
});

test("a page past the first names its number before the brand", () => {
  assert.equal(listingTitle("Зеркала", 2), "Зеркала на заказ в Санкт-Петербурге — страница 2 — Memiro");
  assert.equal(pagedTitle("Зеркала в раме на заказ — memiro", 3), "Зеркала в раме на заказ — страница 3 — memiro");
  assert.equal(pagedTitle("Круглые зеркала", 2), "Круглые зеркала — страница 2");
  assert.equal(pagedTitle("Круглые зеркала", 1), "Круглые зеркала");
});

test("a listing description counts its models from the cheapest one", () => {
  assert.equal(
    listingDescription("Зеркала", 88, "4990.00"),
    `Зеркала на заказ: 88 моделей от 4${NBSP}990 ₽. Размер, форма, подсветка и рама под ваш интерьер. Собственное производство, доставка и монтаж.`,
  );
  assert.equal(
    listingDescription("Зеркала", 3, null),
    "Зеркала на заказ: 3 модели. Размер, форма, подсветка и рама под ваш интерьер. Собственное производство, доставка и монтаж.",
  );
});
