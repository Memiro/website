import type { CalculatorState, PricePresentation } from "./calculator-state.ts";
import type { AttributeSelection, ProductCard } from "./catalog-api.ts";

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

export interface SubmitInquiryRequest {
  source: "SELECTION";
  name: string;
  phone: string;
  email: string | null;
  consent: boolean;
  comment: string;
  items: Array<{
    product_id: string;
    width_mm: number;
    height_mm: number;
    selections: AttributeSelection[];
    wish: string;
  }>;
}

export function canAddCalculatorConfiguration(
  kind: InquiryPresentationKind | undefined,
  wish: string,
): boolean {
  return kind === "priced" || (kind === "wish" && wish.trim().length > 0);
}

export function canShowInquiryEditor(
  kind: InquiryPresentationKind | undefined,
): boolean {
  return kind === "priced" || kind === "wish";
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
  kind: "priced" | "wish",
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

export function selectionInquiry(items: InquiryItem[], contacts: InquiryContacts): SubmitInquiryRequest {
  return {
    source: "SELECTION",
    name: contacts.name,
    phone: contacts.phone,
    email: contacts.email || null,
    consent: contacts.consent,
    comment: "",
    items: items.map((item) => ({
      product_id: item.productId,
      width_mm: item.widthMm,
      height_mm: item.heightMm,
      selections: item.selections.map((selection) => ({
        attribute_id: selection.attributeId,
        value_id: selection.valueId,
        quantity: selection.quantity,
      })),
      wish: item.wish,
    })),
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
