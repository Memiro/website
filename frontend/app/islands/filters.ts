import { isCategoryPage } from "../lib/catalog-api.ts";
import { requestJson } from "../lib/http.ts";
import { productPlural } from "../lib/plural.ts";

// A tick of a checkbox is one keystroke away from the next one, and a price is typed
// digit by digit: the count waits for the visitor to stop before it asks the API.
const COUNT_DELAY_MS = 250;

/** The filter sidebar: a drawer on a phone, and a sort control that submits itself. */
export function mountFilters(root: Document): void {
  const drawer = root.querySelector<HTMLElement>("[data-drawer]");
  const backdrop = root.querySelector<HTMLElement>(".drawer-backdrop");
  const open = root.querySelector<HTMLElement>("[data-drawer-open]");
  const close = (): void => {
    drawer?.classList.remove("open");
    open?.setAttribute("aria-expanded", "false");
    if (backdrop !== null) {
      backdrop.hidden = true;
    }
  };
  open?.addEventListener("click", () => {
    drawer?.classList.add("open");
    open.setAttribute("aria-expanded", "true");
    if (backdrop !== null) {
      backdrop.hidden = false;
    }
  });
  for (const button of root.querySelectorAll("[data-drawer-close]")) {
    button.addEventListener("click", close);
  }
  const sort = root.querySelector<HTMLSelectElement>("[data-sort]");
  sort?.addEventListener("change", () => sort.form?.requestSubmit());
  const form = root.querySelector<HTMLFormElement>("[data-filters]");
  if (form !== null) {
    mountApplyCount(form);
  }
}

/** How many products the narrowing the visitor is still assembling would leave. */
export async function countProducts(
  categorySlug: string,
  search: string,
  apiBaseUrl = window.location.origin,
): Promise<number> {
  const url = new URL(`/api/catalog/categories/${encodeURIComponent(categorySlug)}/products`, apiBaseUrl);
  url.search = search;
  return (await requestJson({ url, isBody: isCategoryPage })).total;
}

/** The label of a button that promises a count: "Показать 12 товаров". */
export function applyLabel(total: number | null): string {
  return total === null ? "Показать" : `Показать ${total} ${productPlural(total)}`;
}

// The count rendered on the server belongs to the filters already applied. Until the
// visitor submits, the button says what his current ticks would actually bring.
function mountApplyCount(form: HTMLFormElement): void {
  const apply = form.querySelector<HTMLElement>("[data-apply]");
  const categorySlug = form.dataset.category ?? "";
  if (apply === null || categorySlug === "") {
    return;
  }
  const applied = apply.textContent ?? "";
  const untouched = narrowing(form);
  let latest = 0;
  let timer: ReturnType<typeof setTimeout> | undefined;
  const count = (search: string): void => {
    const request = ++latest;
    countProducts(categorySlug, search).then(
      (total) => {
        if (request === latest) {
          apply.textContent = applyLabel(total);
        }
      },
      () => undefined,
    );
  };
  const sync = (): void => {
    clearTimeout(timer);
    const search = narrowing(form);
    if (search === untouched) {
      latest += 1;
      apply.textContent = applied;
      return;
    }
    // An answer is a moment away, and a stale number in the meantime is the very thing
    // that misleads: the button drops the count until the new one arrives.
    apply.textContent = applyLabel(null);
    timer = setTimeout(() => count(search), COUNT_DELAY_MS);
  };
  form.addEventListener("input", sync);
  form.addEventListener("change", sync);
}

/** The narrowing the form currently carries, as the query string the API is asked with. */
function narrowing(form: HTMLFormElement): string {
  const params = new URLSearchParams();
  for (const field of form.querySelectorAll<HTMLInputElement>("input")) {
    if (field.type === "checkbox" ? field.checked : field.value !== "") {
      params.append(field.name, field.value);
    }
  }
  return params.toString();
}
