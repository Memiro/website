import { CONTACTS, SITE_NAME } from "./contacts.ts";

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
  telephone: string;
  email: string;
  address: PostalAddressDocument;
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

export function businessJsonLd(site: URL | undefined): BusinessDocument {
  const sameAs = [CONTACTS.telegram, CONTACTS.vk, CONTACTS.maxLink].filter((link) => link !== "");
  return {
    "@context": "https://schema.org",
    "@type": "LocalBusiness",
    name: SITE_NAME,
    description: "Производство интерьерных зеркал на заказ в Санкт-Петербурге: изготовление, доставка и установка.",
    url: absoluteUrl(site, "/") ?? undefined,
    telephone: CONTACTS.phone,
    email: CONTACTS.email,
    address: {
      "@type": "PostalAddress",
      addressCountry: "RU",
      addressLocality: CONTACTS.city,
      streetAddress: CONTACTS.street,
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
