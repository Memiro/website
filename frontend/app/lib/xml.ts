// XML 1.0 has no way to spell most control characters, and one of them in a
// description would break the whole document instead of one element.
const CONTROL = /[\u0000-\u0008\u000B\u000C\u000E-\u001F]/g;

/** Text made safe inside an XML element or attribute. */
export function escapeXml(text: string): string {
  return text
    .replaceAll(CONTROL, "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&apos;");
}

/** An absolute address on the site, made safe inside an XML element. */
export function xmlLink(site: URL, path: string): string {
  return escapeXml(new URL(path, site.origin).href);
}
