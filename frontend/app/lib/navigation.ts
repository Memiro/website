export interface NavigationLink {
  href: string;
  label: string;
}

export const HEADER_LINKS: readonly NavigationLink[] = [
  { href: "/catalog/", label: "Каталог" },
  { href: "/works/", label: "Наши работы" },
  { href: "/about/", label: "О нас" },
  { href: "/delivery/", label: "Доставка и возврат" },
  { href: "/contacts/", label: "Контакты" },
];

export const FOOTER_LEGAL_LINKS: readonly NavigationLink[] = [
  { href: "/privacy/", label: "Политика обработки персональных данных" },
];

export const INQUIRY_LINK: NavigationLink = { href: "/cart/", label: "Заявка" };

export const SITE_LINKS: readonly NavigationLink[] = [
  ...HEADER_LINKS,
  ...FOOTER_LEGAL_LINKS,
  INQUIRY_LINK,
];

/** Anchor attributes that open an outside address in a new tab without handing it the opener. */
export function externalLinkAttrs(external: boolean): { target?: "_blank"; rel?: "noopener" } {
  return external ? { target: "_blank", rel: "noopener" } : {};
}

/** The public address of a product card, spelled in one place for every page that links to one. */
export function productPath(categorySlug: string, productSlug: string): string {
  return `/catalog/${categorySlug}/${productSlug}/`;
}

/** The public address of a category listing. */
export function categoryPath(slug: string): string {
  return `/catalog/${slug}/`;
}

/** The public address of a landing: the owner's own slug sits at the root. */
export function landingPath(slug: string): string {
  return `/${slug}/`;
}

// A section link is current for everything beneath it, but the root is not a
// section: by prefix alone "/" would light up on every page of the site.
export function isCurrentPath(pathname: string, href: string): boolean {
  const normalized = pathname.endsWith("/") ? pathname : `${pathname}/`;
  return href === "/" ? normalized === "/" : normalized.startsWith(href);
}
