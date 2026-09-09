import { pricePresentation } from "./calculator-state.ts";
import type { CalculatorState, PricePresentation } from "./calculator-state.ts";
import { asRecord } from "./http.ts";
import { isVerdict } from "./catalog-api.ts";
import type { AttributeSelection, PricingVerdict, ProductCard } from "./catalog-api.ts";

export interface InquiryItem {
  productId: string;
  productName: string;
  widthMm: number;
  heightMm: number;
  selections: CalculatorState["selections"];
  wish: string;
  isWish: boolean;
}

interface BrowserStorage {
  getItem(key: string): string | null;
  setItem(key: string, value: string): void;
}

const INQUIRY_ITEMS_STORAGE_KEY = "memiro.inquiry-items";
type InquiryPresentationKind = PricePresentation["kind"];

export interface InquiryContacts {
  name: string;
  phone: string;
  email: string;
  consent: boolean;
}

export type InquirySource = "SELECTION" | "FREE_FORM";

export interface InquiryItemRequest {
  product_id: string;
  width_mm: number;
  height_mm: number;
  selections: AttributeSelection[];
  wish: string;
}

export interface SubmitInquiryRequest {
  source: InquirySource;
  name: string;
  phone: string;
  email: string | null;
  consent: boolean;
  comment: string;
  items: InquiryItemRequest[];
}

export interface PreviewInquiryRequest {
  items: InquiryItemRequest[];
}

export interface PreviewedValue {
  attribute_name: string;
  value_name: string | null;
  quantity: string | null;
}

export interface PreviewedConfiguration {
  width_mm: number;
  height_mm: number;
  values: PreviewedValue[];
}

/** One position as the server would store it — or an empty one when the product is gone. */
export interface PreviewedItem {
  product_id: string;
  is_available: boolean;
  product_name: string | null;
  price_from: string | null;
  verdict: PricingVerdict | null;
  price: string | null;
  configuration: PreviewedConfiguration | null;
  wish: string;
}

export interface InquiryPreview {
  items: PreviewedItem[];
}

// A position without a price is still a position (``Inquiry``, rule 7): the
// only configuration there is nothing to add is the one of a product outside
// the calculable set, where the customer configured nothing at all.
const ADDABLE_KINDS: ReadonlySet<InquiryPresentationKind> = new Set(["priced", "hidden", "unpriced", "wish"]);

export function canAddCalculatorConfiguration(
  kind: InquiryPresentationKind | undefined,
  wish: string,
): boolean {
  if (kind === undefined || !ADDABLE_KINDS.has(kind)) {
    return false;
  }
  return kind !== "wish" || wish.trim().length > 0;
}

export function canShowInquiryEditor(
  kind: InquiryPresentationKind | undefined,
): boolean {
  return kind !== undefined && ADDABLE_KINDS.has(kind);
}

export function loadInquiryItems(storage: BrowserStorage): InquiryItem[] {
  try {
    const saved = storage.getItem(INQUIRY_ITEMS_STORAGE_KEY);
    const parsed = saved === null ? null : (JSON.parse(saved) as unknown);
    return Array.isArray(parsed) && parsed.every(isInquiryItem) ? parsed : [];
  } catch {
    return [];
  }
}

// A browser in private mode refuses to store anything: the basket then lives for this page only.
export function saveInquiryItems(storage: BrowserStorage, items: InquiryItem[]): void {
  try {
    storage.setItem(INQUIRY_ITEMS_STORAGE_KEY, JSON.stringify(items));
  } catch {
    return;
  }
}

export function addInquiryItem(storage: BrowserStorage, items: InquiryItem[], item: InquiryItem): InquiryItem[] {
  const nextItems = [...items, item];
  saveInquiryItems(storage, nextItems);
  return nextItems;
}

export function removeInquiryItem(storage: BrowserStorage, items: InquiryItem[], index: number): InquiryItem[] {
  const nextItems = items.filter((_, itemIndex) => itemIndex !== index);
  saveInquiryItems(storage, nextItems);
  return nextItems;
}

export function inquiryItemFromCalculator(
  product: ProductCard,
  state: CalculatorState,
  kind: InquiryPresentationKind,
  wish = "",
): InquiryItem {
  return {
    productId: product.id,
    productName: product.name,
    widthMm: state.widthMm,
    heightMm: state.heightMm,
    selections: state.selections.map((selection) => ({ ...selection })),
    wish,
    isWish: kind === "wish",
  };
}

export function selectionInquiry(items: InquiryItem[], contacts: InquiryContacts, comment = ""): SubmitInquiryRequest {
  return {
    source: "SELECTION",
    name: contacts.name,
    phone: contacts.phone,
    email: contacts.email || null,
    consent: contacts.consent,
    comment,
    items: requestItems(items),
  };
}

// The preview asks with the very positions the submission will send, so what
// the customer reads on the page is what the manager gets (``Inquiry``, rule 20).
export function previewRequest(items: InquiryItem[]): PreviewInquiryRequest {
  return { items: requestItems(items) };
}

function requestItems(items: InquiryItem[]): InquiryItemRequest[] {
  return items.map((item) => ({
    product_id: item.productId,
    width_mm: item.widthMm,
    height_mm: item.heightMm,
    selections: item.selections.map((selection) => ({
      attribute_id: selection.attributeId,
      value_id: selection.valueId,
      quantity: selection.quantity,
    })),
    wish: item.wish,
  }));
}

export function hasUnavailableItem(items: PreviewedItem[]): boolean {
  return items.some((item) => !item.is_available);
}

// The words are the card's: a position that could not be priced there is
// explained here in the same sentence, and the deltas stay on the card. The
// one exception is the card's call to add the position — here it already is.
export function previewedPricePresentation(item: PreviewedItem): PricePresentation | null {
  if (item.verdict === null) {
    return null;
  }
  const presentation = pricePresentation({ verdict: item.verdict, total: item.price, selection_deltas: [] });
  if (item.verdict === "SELECTION_NOT_PRICEABLE") {
    return { ...presentation, message: "Цену такого сочетания назовёт менеджер." };
  }
  return presentation;
}

export function specificationLine(value: PreviewedValue): string {
  return `${value.attribute_name}: ${value.value_name ?? readableQuantity(value.quantity ?? "")}`;
}

// The wire carries a count in the scale the database keeps it in ("2.5000").
function readableQuantity(quantity: string): string {
  return quantity.replace(/\.0+$|(\.\d*[1-9])0+$/, "$1");
}

export function isInquiryPreview(value: unknown): value is InquiryPreview {
  const items = asRecord(value)?.items;
  return Array.isArray(items) && items.every(isPreviewedItem);
}

export function isPreviewedItem(value: unknown): value is PreviewedItem {
  const item = asRecord(value);
  if (item === null) {
    return false;
  }
  return typeof item.product_id === "string"
    && typeof item.is_available === "boolean"
    && isNullableString(item.product_name)
    && isNullableString(item.price_from)
    && (item.verdict === null || isVerdict(item.verdict))
    && isNullableString(item.price)
    && (item.configuration === null || isPreviewedConfiguration(item.configuration))
    && typeof item.wish === "string";
}

function isPreviewedConfiguration(value: unknown): value is PreviewedConfiguration {
  const configuration = asRecord(value);
  if (configuration === null) {
    return false;
  }
  return typeof configuration.width_mm === "number"
    && typeof configuration.height_mm === "number"
    && Array.isArray(configuration.values)
    && configuration.values.every(isPreviewedValue);
}

function isPreviewedValue(value: unknown): value is PreviewedValue {
  const named = asRecord(value);
  return named !== null
    && typeof named.attribute_name === "string"
    && isNullableString(named.value_name)
    && isNullableString(named.quantity);
}

function isNullableString(value: unknown): value is string | null {
  return value === null || typeof value === "string";
}

/** The free-form inquiry of the home page: a question with a comment and no items. */
export function freeFormInquiry(contacts: InquiryContacts, comment: string): SubmitInquiryRequest {
  return {
    source: "FREE_FORM",
    name: contacts.name,
    phone: contacts.phone,
    email: contacts.email || null,
    consent: contacts.consent,
    comment,
    items: [],
  };
}

function isInquiryItem(value: unknown): value is InquiryItem {
  if (typeof value !== "object" || value === null) {
    return false;
  }
  const item = value as Record<string, unknown>;
  return typeof item.productId === "string"
    && typeof item.productName === "string"
    && typeof item.widthMm === "number"
    && typeof item.heightMm === "number"
    && Array.isArray(item.selections)
    && typeof item.wish === "string"
    && typeof item.isWish === "boolean";
}
