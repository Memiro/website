import { API_TIMEOUT_MS, asRecord, requestJson } from "./http.ts";

export type PricingVerdict = "PRICED" | "BEYOND_LIMITS" | "NOT_PRICEABLE" | "SELECTION_NOT_PRICEABLE" | "HIDDEN";

const DEFAULT_INTERNAL_API_BASE_URL = "http://api:8000";

export interface ListEnvelope<Item> {
  items: Item[];
  total: number;
  page: number;
}

export const CATALOG_SORTS = ["name", "cheapest", "dearest"] as const;

export type CatalogSort = (typeof CATALOG_SORTS)[number];

export interface FilterOption {
  value_id: string;
  name: string;
  count: number;
  is_selected: boolean;
}

export interface FilterGroup {
  attribute_id: string;
  name: string;
  options: FilterOption[];
}

export interface PriceBounds {
  lowest: string | null;
  highest: string | null;
  selected_min: string | null;
  selected_max: string | null;
}

export interface CategoryPage extends ListEnvelope<ProductSummary> {
  pages: number;
  groups: FilterGroup[];
  price: PriceBounds | null;
  sort: CatalogSort;
}

export interface LandingSummary {
  slug: string;
  heading: string;
}

export interface Landing extends LandingSummary {
  title: string;
  description: string;
  text: string;
  category_slug: string;
  category_name: string;
  values: string[];
}

export interface Category {
  name: string;
  slug: string;
}

export interface ProductSummary {
  name: string;
  slug: string;
  price_from: string | null;
  image_keys: string[];
}

export interface ProductAttributeValue {
  id: string | null;
  name: string;
  quantity: string | null;
}

/** How a customer configures an attribute: a dictionary row he picks, or a number he types. */
export type AttributeKind = "select" | "number";

export interface ProductAttribute {
  id: string;
  name: string;
  kind: AttributeKind;
  is_customer_changeable: boolean;
  /** The row the product itself is made of; a numeric attribute declares a quantity instead. */
  declared_value_id: string | null;
  values: ProductAttributeValue[];
}

/** One attribute choice on the wire: a declared value, a typed quantity, or the product's own default. */
export interface AttributeSelection {
  attribute_id: string;
  value_id: string | null;
  quantity: string | null;
}

export interface ProductVariant {
  width_mm: number;
  height_mm: number;
  price: string;
  overrides: AttributeSelection[];
}

export interface ProductCard extends ProductSummary {
  id: string;
  description: string;
  attributes: ProductAttribute[];
  variants: ProductVariant[];
}

export interface CalculateRequest {
  product_id: string;
  width_mm: number;
  height_mm: number;
  selections: AttributeSelection[];
}

export interface SelectionDelta {
  attribute_id: string;
  value_id: string | null;
  delta: string;
}

export interface CalculatedPrice {
  verdict: PricingVerdict;
  total: string | null;
  selection_deltas: SelectionDelta[];
  size_surcharge_from_long_side_mm?: number | null;
}

export class CatalogApi {
  private readonly baseUrl: string;
  private readonly timeoutMs: number;

  public constructor(baseUrl: string, timeoutMs: number = API_TIMEOUT_MS) {
    this.baseUrl = baseUrl;
    this.timeoutMs = timeoutMs;
  }

  public async categories(): Promise<ListEnvelope<Category>> {
    return this.get("/catalog/categories", listOf(isCategory));
  }

  public async categoryProducts(slug: string, search = ""): Promise<CategoryPage> {
    const path = `/catalog/categories/${encodeURIComponent(slug)}/products`;
    return this.get(search === "" ? path : `${path}?${search}`, isCategoryPage);
  }

  public async landings(): Promise<ListEnvelope<LandingSummary>> {
    return this.get("/catalog/landings", listOf(isLandingSummary));
  }

  public async landing(slug: string): Promise<Landing> {
    return this.get(`/catalog/landings/${encodeURIComponent(slug)}`, isLanding);
  }

  public async product(slug: string): Promise<ProductCard> {
    return this.get(`/catalog/products/${encodeURIComponent(slug)}`, isProductCard);
  }

  private async get<Body>(path: string, isBody: (value: unknown) => value is Body): Promise<Body> {
    return requestJson({ url: new URL(path, this.baseUrl), isBody, timeoutMs: this.timeoutMs });
  }
}

/** The catalogue as the server-rendered pages reach it — over the contour's internal address. */
export function internalCatalogApi(): CatalogApi {
  return new CatalogApi(import.meta.env.API_INTERNAL_URL ?? DEFAULT_INTERNAL_API_BASE_URL);
}

export function isCalculatedPrice(value: unknown): value is CalculatedPrice {
  const price = asRecord(value);
  if (price === null) {
    return false;
  }
  return isVerdict(price.verdict)
    && isNullableString(price.total)
    && isArrayOf(price.selection_deltas, isSelectionDelta);
}

function isLandingSummary(value: unknown): value is LandingSummary {
  const landing = asRecord(value);
  return landing !== null && typeof landing.slug === "string" && typeof landing.heading === "string";
}

function isLanding(value: unknown): value is Landing {
  const landing = asRecord(value);
  if (landing === null || !isLandingSummary(value)) {
    return false;
  }
  return typeof landing.title === "string"
    && typeof landing.description === "string"
    && typeof landing.text === "string"
    && typeof landing.category_slug === "string"
    && typeof landing.category_name === "string"
    && isArrayOf(landing.values, (item): item is string => typeof item === "string");
}

export function isCategoryPage(value: unknown): value is CategoryPage {
  const page = asRecord(value);
  if (page === null || !listOf(isProductSummary)(value)) {
    return false;
  }
  return typeof page.pages === "number"
    && isCatalogSort(page.sort)
    && isArrayOf(page.groups, isFilterGroup)
    && (page.price === null || isPriceBounds(page.price));
}

function isCatalogSort(value: unknown): value is CatalogSort {
  return CATALOG_SORTS.some((sort) => sort === value);
}

function isFilterGroup(value: unknown): value is FilterGroup {
  const group = asRecord(value);
  if (group === null) {
    return false;
  }
  return typeof group.attribute_id === "string"
    && typeof group.name === "string"
    && isArrayOf(group.options, isFilterOption);
}

function isFilterOption(value: unknown): value is FilterOption {
  const option = asRecord(value);
  if (option === null) {
    return false;
  }
  return typeof option.value_id === "string"
    && typeof option.name === "string"
    && typeof option.count === "number"
    && typeof option.is_selected === "boolean";
}

function isPriceBounds(value: unknown): value is PriceBounds {
  const bounds = asRecord(value);
  if (bounds === null) {
    return false;
  }
  return isNullableString(bounds.lowest)
    && isNullableString(bounds.highest)
    && isNullableString(bounds.selected_min)
    && isNullableString(bounds.selected_max);
}

function listOf<Item>(isItem: (value: unknown) => value is Item): (value: unknown) => value is ListEnvelope<Item> {
  return (value): value is ListEnvelope<Item> => {
    const envelope = asRecord(value);
    if (envelope === null) {
      return false;
    }
    return isArrayOf(envelope.items, isItem)
      && typeof envelope.total === "number"
      && typeof envelope.page === "number";
  };
}

function isCategory(value: unknown): value is Category {
  const category = asRecord(value);
  return category !== null && typeof category.name === "string" && typeof category.slug === "string";
}

function isProductSummary(value: unknown): value is ProductSummary {
  const product = asRecord(value);
  if (product === null) {
    return false;
  }
  return typeof product.name === "string"
    && typeof product.slug === "string"
    && isNullableString(product.price_from)
    && isArrayOf(product.image_keys, isString);
}

function isProductCard(value: unknown): value is ProductCard {
  const product = asRecord(value);
  if (product === null || !isProductSummary(value)) {
    return false;
  }
  return typeof product.id === "string"
    && typeof product.description === "string"
    && isArrayOf(product.attributes, isProductAttribute)
    && isArrayOf(product.variants, isProductVariant);
}

function isProductAttribute(value: unknown): value is ProductAttribute {
  const attribute = asRecord(value);
  if (attribute === null) {
    return false;
  }
  return typeof attribute.id === "string"
    && typeof attribute.name === "string"
    && isAttributeKind(attribute.kind)
    && isNullableString(attribute.declared_value_id)
    && typeof attribute.is_customer_changeable === "boolean"
    && isArrayOf(attribute.values, isProductAttributeValue);
}

function isProductAttributeValue(value: unknown): value is ProductAttributeValue {
  const attributeValue = asRecord(value);
  if (attributeValue === null) {
    return false;
  }
  return isNullableString(attributeValue.id)
    && typeof attributeValue.name === "string"
    && isNullableString(attributeValue.quantity);
}

function isAttributeKind(value: unknown): value is AttributeKind {
  return value === "select" || value === "number";
}

function isProductVariant(value: unknown): value is ProductVariant {
  const variant = asRecord(value);
  if (variant === null) {
    return false;
  }
  return typeof variant.width_mm === "number"
    && typeof variant.height_mm === "number"
    && typeof variant.price === "string"
    && isArrayOf(variant.overrides, isAttributeSelection);
}

function isAttributeSelection(value: unknown): value is AttributeSelection {
  const selection = asRecord(value);
  if (selection === null) {
    return false;
  }
  return typeof selection.attribute_id === "string"
    && isNullableString(selection.value_id)
    && isNullableString(selection.quantity);
}

function isSelectionDelta(value: unknown): value is SelectionDelta {
  const delta = asRecord(value);
  if (delta === null) {
    return false;
  }
  return typeof delta.attribute_id === "string"
    && isNullableString(delta.value_id)
    && typeof delta.delta === "string";
}

function isVerdict(value: unknown): value is PricingVerdict {
  return value === "PRICED" || value === "BEYOND_LIMITS" || value === "NOT_PRICEABLE"
    || value === "SELECTION_NOT_PRICEABLE" || value === "HIDDEN";
}

function isArrayOf<Item>(value: unknown, isItem: (item: unknown) => item is Item): value is Item[] {
  return Array.isArray(value) && value.every(isItem);
}

function isString(value: unknown): value is string {
  return typeof value === "string";
}

function isNullableString(value: unknown): value is string | null {
  return value === null || typeof value === "string";
}
