import { FIRST_PAGE, isNarrowed, type CatalogQuery } from "./catalog-query.ts";
import { SITE_NAME } from "./site.ts";
import type { Contacts } from "./site-api.ts";

export interface Crumb {
  href: string;
  label: string;
}

/** The site's public origin; canonical and og:url are absolute or absent. */
export function siteOrigin(site: URL | undefined): string | null {
  return site === undefined ? null : site.origin;
}

export function absoluteUrl(site: URL | undefined, path: string): string | null {
  const origin = siteOrigin(site);
  return origin === null ? null : new URL(path, origin).href;
}

/**
 * The address a listing declares as its own. A narrowing shows the category
 * under another address and folds onto the clean one (ADR-0003); a page number
 * shows different products and stands on its own. Pointing a page at the first
 * one while also refusing it indexing makes the two signals contradict, and the
 * refusal risks being read against the category itself.
 */
export function listingCanonicalPath(path: string, query: CatalogQuery): string {
  if (isNarrowed(query) || query.page === FIRST_PAGE) {
    return path;
  }
  return `${path}?page=${query.page}`;
}

/** Only a narrowing is kept out of the index; paging is the way to the products past the first page. */
export function listingRobots(query: CatalogQuery): string | undefined {
  return isNarrowed(query) ? "noindex, follow" : undefined;
}

export interface PostalAddressDocument {
  "@type": "PostalAddress";
  addressCountry: string;
  addressLocality: string;
  streetAddress: string;
}

export interface BusinessDocument {
  "@context": string;
  "@type": "LocalBusiness";
  name: string;
  description: string;
  url: string | undefined;
  telephone: string | undefined;
  email: string | undefined;
  address: PostalAddressDocument | undefined;
  sameAs: string[] | undefined;
}

export interface OfferDocument {
  "@type": "Offer";
  priceCurrency: string;
  price: string;
  availability: string;
  url: string | undefined;
}

export interface ProductDocument {
  "@context": string;
  "@type": "Product";
  name: string;
  description: string;
  url: string | undefined;
  image: string | undefined;
  brand: { "@type": "Brand"; name: string };
  offers: OfferDocument | undefined;
}

export interface ListItemDocument {
  "@type": "ListItem";
  position: number;
  name: string;
  item: string | undefined;
}

export interface BreadcrumbsDocument {
  "@context": string;
  "@type": "BreadcrumbList";
  itemListElement: ListItemDocument[];
}

export interface OrganizationDocument {
  "@context": string;
  "@type": "Organization";
  name: string;
  url: string | undefined;
  logo: string | undefined;
}

export interface ItemListEntryDocument {
  "@type": "ListItem";
  position: number;
  name: string;
  url: string | undefined;
}

export interface ItemListDocument {
  "@context": string;
  "@type": "ItemList";
  itemListElement: ItemListEntryDocument[];
}

export type JsonLdDocument =
  | BusinessDocument
  | ProductDocument
  | BreadcrumbsDocument
  | OrganizationDocument
  | ItemListDocument;

// Markup never names a profile the owner has not entered: an invented link is
// a worse answer to a search engine than no link at all.
export function businessJsonLd(site: URL | undefined, contacts: Contacts | null): BusinessDocument {
  const sameAs = [contacts?.telegram, contacts?.vk, contacts?.max_link].filter(
    (link): link is string => link !== undefined && link !== "",
  );
  return {
    "@context": "https://schema.org",
    "@type": "LocalBusiness",
    name: SITE_NAME,
    description: "Производство интерьерных зеркал на заказ в Санкт-Петербурге: изготовление, доставка и установка.",
    url: absoluteUrl(site, "/") ?? undefined,
    telephone: contacts?.phone,
    email: contacts?.email,
    address: contacts === null ? undefined : {
      "@type": "PostalAddress",
      addressCountry: "RU",
      addressLocality: contacts.city,
      streetAddress: contacts.street,
    },
    sameAs: sameAs.length > 0 ? sameAs : undefined,
  };
}

export interface ProductJsonLdInput {
  name: string;
  description: string;
  url: string | null;
  image: string | null;
  priceFrom: string | null;
}

export function productJsonLd(product: ProductJsonLdInput): ProductDocument {
  return {
    "@context": "https://schema.org",
    "@type": "Product",
    name: product.name,
    description: product.description,
    url: product.url ?? undefined,
    image: product.image ?? undefined,
    brand: { "@type": "Brand", name: SITE_NAME },
    // Made to order: the card names the cheapest precalculated configuration,
    // never a price the visitor can pay on the site.
    offers: product.priceFrom === null
      ? undefined
      : {
        "@type": "Offer",
        priceCurrency: "RUB",
        price: product.priceFrom,
        availability: "https://schema.org/MadeToOrder",
        url: product.url ?? undefined,
      },
  };
}

export function breadcrumbsJsonLd(site: URL | undefined, crumbs: Crumb[]): BreadcrumbsDocument {
  return {
    "@context": "https://schema.org",
    "@type": "BreadcrumbList",
    itemListElement: crumbs.map((crumb, index) => ({
      "@type": "ListItem",
      position: index + 1,
      name: crumb.label,
      item: absoluteUrl(site, crumb.href) ?? undefined,
    })),
  };
}

/** The studio as an organisation: what puts its logo beside the name in a knowledge panel. */
export function organizationJsonLd(site: URL | undefined): OrganizationDocument {
  return {
    "@context": "https://schema.org",
    "@type": "Organization",
    name: SITE_NAME,
    url: absoluteUrl(site, "/") ?? undefined,
    logo: absoluteUrl(site, "/img/logo.png") ?? undefined,
  };
}

/**
 * What a listing shows, in the order it shows it. Positions count from the top
 * of the page and not of the catalogue: the document describes this address.
 * An empty listing declares nothing — a list of nothing is worse than silence.
 */
export function itemListJsonLd(site: URL | undefined, entries: Crumb[]): ItemListDocument | null {
  if (entries.length === 0) {
    return null;
  }
  return {
    "@context": "https://schema.org",
    "@type": "ItemList",
    itemListElement: entries.map((entry, index) => ({
      "@type": "ListItem",
      position: index + 1,
      name: entry.label,
      url: absoluteUrl(site, entry.href) ?? undefined,
    })),
  };
}
