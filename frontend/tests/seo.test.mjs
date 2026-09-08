import assert from "node:assert/strict";
import test from "node:test";

import { absoluteUrl, breadcrumbsJsonLd, businessJsonLd, itemListJsonLd, listingCanonicalPath, listingRobots, organizationJsonLd, productJsonLd } from "../app/lib/seo.ts";

const SITE = new URL("https://memiro.ru");

test("a canonical address is absolute when the site origin is known", () => {
  assert.equal(absoluteUrl(SITE, "/catalog/mirrors/"), "https://memiro.ru/catalog/mirrors/");
});

test("a page of a site without a configured origin gets no canonical address", () => {
  assert.equal(absoluteUrl(undefined, "/catalog/"), null);
});

test("the business document names the studio and the city its contacts give", () => {
  /** @type {import("../app/lib/site-api.ts").Contacts} */
  const contacts = {
    city: "Санкт-Петербург",
    street: "Александра Матросова, 4к2ж",
    phone: "+79812304050",
    phone_display: "+7 981 230-40-50",
    email: "memiro.ru@yandex.ru",
    hours: "",
    max_link: "",
    telegram: "https://t.me/memiro_shop",
    vk: "",
    map_embed: "",
  };

  const business = businessJsonLd(SITE, contacts);

  assert.equal(business["@type"], "LocalBusiness");
  assert.equal(business.address?.addressLocality, "Санкт-Петербург");
  assert.deepEqual(business.sameAs, ["https://t.me/memiro_shop"]);
});

test("a site whose contacts nobody entered publishes no address and no profiles", () => {
  const business = businessJsonLd(SITE, null);

  assert.equal(business.address, undefined);
  assert.equal(business.sameAs, undefined);
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

// A narrowing shows the category under another address, so it canonicalises to
// the clean one (ADR-0003). A page number shows different products, so it
// canonicalises to itself — pointing it at page 1 while also refusing it makes
// the two signals contradict, and the refusal risks reaching the category.
test("a page of a listing is its own canonical address", () => {
  const query = { values: [], priceMin: "", priceMax: "", sort: /** @type {const} */ ("name"), page: 3 };
  assert.equal(listingCanonicalPath("/catalog/mirrors/", query), "/catalog/mirrors/?page=3");
});

test("the first page carries no page number and so no duplicate", () => {
  const query = { values: [], priceMin: "", priceMax: "", sort: /** @type {const} */ ("name"), page: 1 };
  assert.equal(listingCanonicalPath("/catalog/mirrors/", query), "/catalog/mirrors/");
});

test("a narrowing canonicalises to the clean listing, on any page", () => {
  const query = { values: ["v1"], priceMin: "", priceMax: "", sort: /** @type {const} */ ("name"), page: 2 };
  assert.equal(listingCanonicalPath("/catalog/mirrors/", query), "/catalog/mirrors/");
  const priced = { values: [], priceMin: "1000", priceMax: "", sort: /** @type {const} */ ("name"), page: 1 };
  assert.equal(listingCanonicalPath("/catalog/mirrors/", priced), "/catalog/mirrors/");
});

test("only a narrowing is refused indexing; a page number is not", () => {
  assert.equal(listingRobots({ values: [], priceMin: "", priceMax: "", sort: /** @type {const} */ ("name"), page: 4 }), undefined);
  assert.equal(listingRobots({ values: ["v1"], priceMin: "", priceMax: "", sort: /** @type {const} */ ("name"), page: 1 }), "noindex, follow");
});

// Sorting reorders the same products: it stays indexable and folds onto the
// clean address, which is what it already did.
test("sorting does not create an address of its own", () => {
  const query = { values: [], priceMin: "", priceMax: "", sort: /** @type {const} */ ("cheapest"), page: 1 };
  assert.equal(listingCanonicalPath("/catalog/mirrors/", query), "/catalog/mirrors/");
  assert.equal(listingRobots(query), undefined);
});

test("the organisation is named with a logo a crawler can fetch", () => {
  const document = organizationJsonLd(SITE);
  assert.equal(document["@type"], "Organization");
  assert.equal(document.name, "Memiro");
  assert.equal(document.logo, "https://memiro.ru/img/logo.png");
  assert.equal(document.url, "https://memiro.ru/");
});

test("a listing offers its items in the order the page shows them", () => {
  const document = itemListJsonLd(SITE, [
    { href: "/catalog/zerkala/kolo/", label: "Кольцо" },
    { href: "/catalog/zerkala/echo/", label: "Эхо" },
  ]);
  assert.ok(document !== null);
  assert.equal(document["@type"], "ItemList");
  assert.deepEqual(document.itemListElement, [
    { "@type": "ListItem", position: 1, name: "Кольцо", url: "https://memiro.ru/catalog/zerkala/kolo/" },
    { "@type": "ListItem", position: 2, name: "Эхо", url: "https://memiro.ru/catalog/zerkala/echo/" },
  ]);
});

// Position counts from the top of the page, not of the catalogue: the document
// describes what this address shows.
test("the second page numbers its items from one", () => {
  const document = itemListJsonLd(SITE, [{ href: "/catalog/zerkala/nave/", label: "Неф" }]);
  assert.ok(document !== null);
  assert.equal(document.itemListElement[0].position, 1);
});

test("an empty listing has no list to declare", () => {
  assert.equal(itemListJsonLd(SITE, []), null);
});
