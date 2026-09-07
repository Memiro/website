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

export type JsonLdDocument = BusinessDocument | ProductDocument | BreadcrumbsDocument;

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
