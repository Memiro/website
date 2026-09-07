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
}
