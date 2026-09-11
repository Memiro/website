import { API_TIMEOUT_MS, asRecord, requestJson } from "./http.ts";
import { internalApiBaseUrl } from "./internal-api.ts";

export interface Contacts {
  city: string;
  street: string;
  phone: string;
  phone_display: string;
  email: string;
  hours: string;
  max_link: string;
  telegram: string;
  vk: string;
  map_embed: string;
}

export type RequisiteKind = "name" | "ogrn" | "inn" | "address";

const REQUISITE_KINDS: readonly RequisiteKind[] = ["name", "ogrn", "inn", "address"];

// The caption each requisite is printed under; the seller's own name carries
// none — it reads as the name of the seller.
const REQUISITE_LABELS: Record<RequisiteKind, string> = {
  name: "",
  ogrn: "ОГРН/ОГРНИП",
  inn: "ИНН",
  address: "Адрес",
};

export interface Requisite {
  kind: RequisiteKind;
  value: string;
}

export interface SiteLink {
  label: string;
  value: string;
}

/** The caption a requisite is printed under, empty for the seller's own name. */
export function requisiteLabel(kind: RequisiteKind): string {
  return REQUISITE_LABELS[kind];
}

export interface Site {
  contacts: Contacts | null;
  seller: Requisite[];
}

export const EMPTY_SITE: Site = { contacts: null, seller: [] };

/** The studio's address, the way the storefront prints it in one line. */
export function addressLine(contacts: Contacts): string {
  return [contacts.city, contacts.street].filter((part) => part !== "").join(", ");
}

/** Links to the studio outside the site, in the order the storefront prints them. */
export function socialLinks(contacts: Contacts): SiteLink[] {
  return [
    { label: "MAX", value: contacts.max_link },
    { label: "Telegram", value: contacts.telegram },
    { label: "ВКонтакте", value: contacts.vk },
  ].filter((link) => link.value !== "");
}

/**
 * Read the site's own data for a server-rendered page.
 *
 * An unreachable API must not take the page down with it: the layout renders
 * without the contact block rather than answering with an error page.
 */
export async function readSite(): Promise<Site> {
  const baseUrl = internalApiBaseUrl();
  try {
    return await requestJson({ url: new URL("/site", baseUrl), isBody: isSite, timeoutMs: API_TIMEOUT_MS });
  } catch {
    return EMPTY_SITE;
  }
}

function isSite(value: unknown): value is Site {
  const site = asRecord(value);
  if (site === null || !Array.isArray(site.seller)) {
    return false;
  }
  return (site.contacts === null || isContacts(site.contacts)) && site.seller.every(isRequisite);
}

function isContacts(value: unknown): value is Contacts {
  const contacts = asRecord(value);
  if (contacts === null) {
    return false;
  }
  const fields = ["city", "street", "phone", "phone_display", "email", "hours", "max_link", "telegram", "vk", "map_embed"];
  return fields.every((field) => typeof contacts[field] === "string");
}

function isRequisite(value: unknown): value is Requisite {
  const requisite = asRecord(value);
  if (requisite === null || typeof requisite.value !== "string") {
    return false;
  }
  return REQUISITE_KINDS.some((kind) => kind === requisite.kind);
}
