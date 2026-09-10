import { CATALOG_SORTS, type CatalogSort } from "./catalog-api.ts";

export interface CatalogQuery {
  values: string[];
  priceMin: string;
  priceMax: string;
  sort: CatalogSort;
  page: number;
}

export const FIRST_PAGE = 1;
export const VALUE_PARAM = "value";
/** The listing as the API gives it unasked: every filter off, by name, the first page. */
export const EMPTY_QUERY: CatalogQuery = { values: [], priceMin: "", priceMax: "", sort: "name", page: FIRST_PAGE };
const SORT_LABELS: Record<CatalogSort, string> = {
  name: "По названию",
  cheapest: "Сначала дешёвые",
  dearest: "Сначала дорогие",
};

/** The orders offered in the sort control, in the order the API names them. */
export const SORT_OPTIONS = CATALOG_SORTS.map((value) => ({ value, label: SORT_LABELS[value] }));

function asSort(value: string | null): CatalogSort {
  return CATALOG_SORTS.find((sort) => sort === value) ?? "name";
}

// Shape only, no version check: the API refuses anything that is not a UUID
// with a 422, and a stray letter in an old link must not take the page down.
const UUID_SHAPE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

function asValues(values: string[]): string[] {
  return values.filter((value) => UUID_SHAPE.test(value));
}

function asPage(value: string | null): number {
  const page = Number(value);
  return Number.isInteger(page) && page >= FIRST_PAGE ? page : FIRST_PAGE;
}

// A price the visitor typed is passed on only when it is a number: a letter
// in the field would turn the whole page into a validation refusal.
function asAmount(value: string | null): string {
  return value !== null && value.trim() !== "" && Number.isFinite(Number(value)) && Number(value) >= 0
    ? String(Number(value))
    : "";
}

export function parseCatalogQuery(params: URLSearchParams): CatalogQuery {
  return {
    values: asValues(params.getAll(VALUE_PARAM)),
    priceMin: asAmount(params.get("price_min")),
    priceMax: asAmount(params.get("price_max")),
    sort: asSort(params.get("sort")),
    page: asPage(params.get("page")),
  };
}

/** Build the query string the API is asked with, leaving out everything at its default. */
export function catalogSearch(query: CatalogQuery): string {
  const params = new URLSearchParams();
  for (const value of query.values) {
    params.append(VALUE_PARAM, value);
  }
  if (query.priceMin !== "") {
    params.set("price_min", query.priceMin);
  }
  if (query.priceMax !== "") {
    params.set("price_max", query.priceMax);
  }
  if (query.sort !== "name") {
    params.set("sort", query.sort);
  }
  if (query.page !== FIRST_PAGE) {
    params.set("page", String(query.page));
  }
  return params.toString();
}

function href(path: string, query: CatalogQuery): string {
  const search = catalogSearch(query);
  return search === "" ? path : `${path}?${search}`;
}

/** The address the page takes when one narrowing is dropped; a narrower page starts at its first page. */
export function withoutValue(path: string, query: CatalogQuery, valueId: string): string {
  return href(path, { ...query, values: query.values.filter((value) => value !== valueId), page: FIRST_PAGE });
}

export function withoutPrice(path: string, query: CatalogQuery): string {
  return href(path, { ...query, priceMin: "", priceMax: "", page: FIRST_PAGE });
}

export function withSort(path: string, query: CatalogQuery, sort: CatalogSort): string {
  return href(path, { ...query, sort, page: FIRST_PAGE });
}

export function withPage(path: string, query: CatalogQuery, page: number): string {
  return href(path, { ...query, page });
}

/** Every page of the listing, in order: the pager of a category prints them all. */
export function pageNumbers(pages: number): number[] {
  return Array.from({ length: pages }, (_, index) => index + 1);
}

/** Whether the visitor asked for a page past the last one; an empty listing still has its first page. */
export function isBeyondLastPage(query: CatalogQuery, pages: number): boolean {
  return query.page > Math.max(pages, FIRST_PAGE);
}

export function isNarrowed(query: CatalogQuery): boolean {
  return query.values.length > 0 || query.priceMin !== "" || query.priceMax !== "";
}
