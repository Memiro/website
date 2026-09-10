// Files and served directories are not pages: a slash after "robots.txt" or
// a hashed asset would answer nothing.
const SERVED_PREFIXES = ["/_astro/", "/media/"];

/** The slashed twin of a page address, or null when the address is already canonical or is not a page. */
export function slashRedirect(pathname: string): string | null {
  if (pathname.endsWith("/") || SERVED_PREFIXES.some((prefix) => pathname.startsWith(prefix))) {
    return null;
  }
  const lastSegment = pathname.slice(pathname.lastIndexOf("/") + 1);
  return lastSegment.includes(".") ? null : `${pathname}/`;
}
