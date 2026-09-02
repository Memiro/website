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

export const FOOTER_CATALOG_LINKS: readonly NavigationLink[] = [
  { href: "/catalog/", label: "Все зеркала" },
  { href: "/works/", label: "Наши работы" },
];

export const FOOTER_CUSTOMER_LINKS: readonly NavigationLink[] = [
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
  ...FOOTER_CUSTOMER_LINKS,
  ...FOOTER_LEGAL_LINKS,
  INQUIRY_LINK,
];

// A section link is current for everything beneath it, but the root is not a
// section: by prefix alone "/" would light up on every page of the site.
export function isCurrentPath(pathname: string, href: string): boolean {
  const normalized = pathname.endsWith("/") ? pathname : `${pathname}/`;
  return href === "/" ? normalized === "/" : normalized.startsWith(href);
}
