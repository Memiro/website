export interface NavigationLink {
  href: string;
  label: string;
}

// Links to pages the storefront does not serve yet are absent on purpose:
// a header link is a promise that the page exists.
export const HEADER_LINKS: readonly NavigationLink[] = [{ href: "/catalog/", label: "Каталог" }];

export const FOOTER_CATALOG_LINKS: readonly NavigationLink[] = [{ href: "/catalog/", label: "Все зеркала" }];

export const FOOTER_LEGAL_LINKS: readonly NavigationLink[] = [
  { href: "/privacy/", label: "Политика обработки персональных данных" },
];

export const SITE_LINKS: readonly NavigationLink[] = [
  ...HEADER_LINKS,
  ...FOOTER_CATALOG_LINKS,
  ...FOOTER_LEGAL_LINKS,
];

// A section link is current for everything beneath it, but the root is not a
// section: by prefix alone "/" would light up on every page of the site.
export function isCurrentPath(pathname: string, href: string): boolean {
  const normalized = pathname.endsWith("/") ? pathname : `${pathname}/`;
  return href === "/" ? normalized === "/" : normalized.startsWith(href);
}
