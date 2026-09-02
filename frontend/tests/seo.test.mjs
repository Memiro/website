import assert from "node:assert/strict";
import test from "node:test";

import { absoluteUrl, breadcrumbsJsonLd, businessJsonLd, productJsonLd } from "../app/lib/seo.ts";

const SITE = new URL("https://memiro.ru");

test("a canonical address is absolute when the site origin is known", () => {
  assert.equal(absoluteUrl(SITE, "/catalog/mirrors/"), "https://memiro.ru/catalog/mirrors/");
});

test("a page of a site without a configured origin gets no canonical address", () => {
  assert.equal(absoluteUrl(undefined, "/catalog/"), null);
});

test("the business document names the studio and its city", () => {
  const business = businessJsonLd(SITE);
  assert.equal(business["@type"], "LocalBusiness");
  assert.equal(business.address.addressLocality, "Санкт-Петербург");
});

test("a product without a precalculated price carries no offer", () => {
  const product = productJsonLd({ name: "Lira", description: "", url: null, image: null, priceFrom: null });
  assert.equal(product.offers, undefined);
});

test("a priced product is offered as made to order", () => {
  const offers = productJsonLd({ name: "Lira", description: "", url: null, image: null, priceFrom: "8900.00" }).offers;

  assert.equal(offers?.price, "8900.00");
  assert.equal(offers?.availability, "https://schema.org/MadeToOrder");
});

test("breadcrumbs are numbered from the home page down", () => {
  const crumbs = breadcrumbsJsonLd(SITE, [{ href: "/", label: "Главная" }, { href: "/catalog/", label: "Каталог" }]);
  assert.deepEqual(crumbs.itemListElement.map((item) => item.position), [1, 2]);
  assert.equal(crumbs.itemListElement[1].item, "https://memiro.ru/catalog/");
});
