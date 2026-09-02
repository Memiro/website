import type { CatalogSort } from "./catalog-api.ts";

export interface CatalogQuery {
  values: string[];
  priceMin: string;
  priceMax: string;
  sort: CatalogSort;
  page: number;
}

export const FIRST_PAGE = 1;
export const VALUE_PARAM = "value";
const SORTS: CatalogSort[] = ["name", "cheapest", "dearest"];

export const SORT_LABELS: { value: CatalogSort; label: string }[] = [
  { value: "name", label: "По названию" },
  { value: "cheapest", label: "Сначала дешёвые" },
  { value: "dearest", label: "Сначала дорогие" },
];

function asSort(value: string | null): CatalogSort {
  return SORTS.find((sort) => sort === value) ?? "name";
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
    values: params.getAll(VALUE_PARAM),
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

/** The pages a visitor may jump to, always including the first, the last and the current one. */
export function pageNumbers(pages: number): number[] {
  return Array.from({ length: pages }, (_, index) => index + 1);
}

export function isNarrowed(query: CatalogQuery): boolean {
  return query.values.length > 0 || query.priceMin !== "" || query.priceMax !== "";
}
