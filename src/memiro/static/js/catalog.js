// Каталог: мгновенное применение фильтров на десктопе, drawer с живым
// счётчиком на мобиле, «Показать ещё» поверх настоящих ?page=n
(() => {
  const form = document.querySelector("[data-filters-form]");
  if (!form) return;

  const desktop = window.matchMedia("(min-width: 961px)");

  // URL текущего выбора формы: пустые значения (sort по умолчанию) не тащим
  const formUrl = () => {
    const params = new URLSearchParams();
    for (const [name, value] of new FormData(form)) {
      if (value !== "") params.append(name, value);
    }
    const query = params.toString();
    return form.action + (query ? `?${query}` : "");
  };

  // --- Drawer мобильных фильтров ---
  const drawer = document.querySelector("[data-drawer]");
  const backdrop = document.querySelector(".drawer-backdrop");
  const setDrawer = (open) => {
    drawer.classList.toggle("open", open);
    if (backdrop) backdrop.hidden = !open;
  };
  document.querySelectorAll("[data-drawer-open]").forEach((button) =>
    button.addEventListener("click", () => setDrawer(true)),
  );
  document.querySelectorAll("[data-drawer-close]").forEach((element) =>
    element.addEventListener("click", () => setDrawer(false)),
  );

  // --- Применение фильтров ---
  const applyCount = form.querySelector("[data-apply-count]");
  const refreshCount = async () => {
    if (!applyCount) return;
    try {
      const response = await fetch(formUrl());
      if (!response.ok) {
        // Пустая комбинация отвечает 404 — товаров ноль
        applyCount.textContent = "0";
        return;
      }
      const html = await response.text();
      const doc = new DOMParser().parseFromString(html, "text/html");
      const total = doc.querySelector("[data-total-count]");
      if (total) applyCount.textContent = total.dataset.totalCount;
    } catch {
      /* сеть моргнула — кнопка остаётся с прежним числом */
    }
  };

  form.addEventListener("change", () => {
    if (desktop.matches) {
      window.location.assign(formUrl());
    } else {
      refreshCount();
    }
  });
  form.addEventListener("submit", (event) => {
    event.preventDefault();
    window.location.assign(formUrl());
  });

  // Селект сортировки живёт вне формы (attribute form=) — применяем сразу
  const sort = document.querySelector("[data-sort]");
  if (sort) {
    sort.addEventListener("change", () => window.location.assign(formUrl()));
  }

  // --- «Показать ещё»: подгрузка следующей настоящей страницы ---
  const grid = document.querySelector("[data-grid]");
  const bindShowMore = () => {
    const link = document.querySelector("[data-show-more]");
    if (!link) return;
    link.addEventListener("click", async (event) => {
      event.preventDefault();
      let doc;
      try {
        const response = await fetch(link.href);
        if (!response.ok) throw new Error(response.status);
        doc = new DOMParser().parseFromString(
          await response.text(),
          "text/html",
        );
      } catch {
        window.location.assign(link.href); // деградация до обычной ссылки
        return;
      }
      const nextGrid = doc.querySelector("[data-grid]");
      if (nextGrid) grid.append(...nextGrid.children);
      const nextMore = doc.querySelector("[data-show-more]");
      const pager = document.querySelector("[data-pager]");
      const nextPager = doc.querySelector("[data-pager]");
      if (pager && nextPager) pager.replaceWith(nextPager);
      history.replaceState(null, "", link.href);
      if (nextMore) {
        link.closest(".show-more").replaceWith(
          nextMore.closest(".show-more"),
        );
        bindShowMore();
      } else {
        link.closest(".show-more").remove();
      }
    });
  };
  bindShowMore();
})();
