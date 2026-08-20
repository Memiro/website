// Избранное, корзина и отправка заявки (тикет 07).
// Подборки живут в localStorage: регистрации нет, сервер о них не знает.
// Названия и цены всегда берутся с сервера — цена остаётся его правдой.
(() => {
  const KEYS = {
    cart: "memiro:cart",
    favorites: "memiro:favorites",
  };
  // Столько же товаров принимают /api/products и /api/leads
  const MAX_ITEMS = 100;
  const LABELS = {
    cart: { on: "В корзине", off: "В корзину" },
    favorites: { on: "В избранном", off: "В избранное" },
  };

  const read = (kind) => {
    try {
      const stored = JSON.parse(localStorage.getItem(KEYS[kind]) || "[]");
      return Array.isArray(stored) ? stored.filter(Number.isInteger) : [];
    } catch {
      // Испорченное хранилище — не повод ронять страницу
      return [];
    }
  };

  const write = (kind, ids) => {
    try {
      localStorage.setItem(KEYS[kind], JSON.stringify(ids));
    } catch {
      // Приватный режим без записи: подборка живёт до перезагрузки
    }
  };

  const toggle = (kind, id) => {
    const ids = read(kind);
    if (ids.includes(id)) {
      write(
        kind,
        ids.filter((stored) => stored !== id),
      );
      return false;
    }
    // Потолок тот же, что у эндпоинтов: длинный список они отвергнут.
    // Кнопка просто не переключится — состояние на экране остаётся честным
    if (ids.length >= MAX_ITEMS) return false;
    write(kind, [...ids, id]);
    return true;
  };

  const remove = (kind, id) => {
    write(
      kind,
      read(kind).filter((stored) => stored !== id),
    );
  };

  // ---------- Синхронизация разметки с хранилищем ----------

  const paintCounters = () => {
    document.querySelectorAll("[data-count]").forEach((badge) => {
      const count = read(badge.dataset.count).length;
      badge.textContent = String(count);
      badge.hidden = count === 0;
    });
  };

  const paintButton = (button) => {
    const kind = button.dataset.toggle;
    const isOn = read(kind).includes(Number(button.dataset.product));
    const labels = LABELS[kind];
    button.setAttribute("aria-pressed", String(isOn));
    button.classList.toggle("on", isOn);
    if (button.dataset.labelOn) {
      // У иконочных кнопок текста нет — им хватает aria-label
      const label = isOn ? labels.on : labels.off;
      const text = [...button.childNodes].find(
        (node) => node.nodeType === Node.TEXT_NODE && node.textContent.trim(),
      );
      if (text) {
        text.textContent = ` ${label}`;
      } else {
        button.textContent = label;
      }
    }
    button.setAttribute("aria-label", isOn ? labels.on : labels.off);
    button.title = isOn ? labels.on : labels.off;
  };

  const paintButtons = (root = document) => {
    root.querySelectorAll("[data-toggle][data-product]").forEach(paintButton);
  };

  const paint = () => {
    paintCounters();
    paintButtons();
  };

  document.addEventListener("click", (event) => {
    const button = event.target.closest("[data-toggle][data-product]");
    if (!button) return;
    event.preventDefault();
    toggle(button.dataset.toggle, Number(button.dataset.product));
    paint();
  });

  // Подборка могла измениться в соседней вкладке
  window.addEventListener("storage", () => {
    paint();
    renderCollections();
  });

  // ---------- Корзина и избранное: строки подборки ----------

  // Разбивка тысяч узким неразрывным пробелом — как фильтр `rub` в шаблонах
  const price = (value) =>
    `от ${String(value).replace(/\B(?=(\d{3})+(?!\d))/g, "\u202F")} ₽`;

  const cartRow = (item) => {
    const row = document.createElement("article");
    row.className = "cart-row";

    const link = document.createElement("a");
    link.className = "cart-pic";
    link.href = item.url;
    if (item.photo) {
      const img = document.createElement("img");
      img.src = item.photo;
      img.alt = item.name;
      img.loading = "lazy";
      link.append(img);
    }

    const meta = document.createElement("div");
    meta.className = "cart-meta";
    const title = document.createElement("a");
    title.className = "cart-name";
    title.href = item.url;
    title.textContent = item.name;
    const category = document.createElement("div");
    category.className = "cart-category";
    category.textContent = item.category;
    meta.append(title, category);

    const cost = document.createElement("div");
    cost.className = "cart-price";
    cost.textContent = price(item.price);

    const drop = document.createElement("button");
    drop.className = "cart-drop";
    drop.type = "button";
    drop.textContent = "Убрать";
    drop.addEventListener("click", () => {
      remove("cart", item.id);
      paint();
      renderCollections();
    });

    row.append(link, meta, cost, drop);
    return row;
  };

  const favoriteCard = (item) => {
    const card = document.createElement("article");
    card.className = "product-card";

    const link = document.createElement("a");
    link.className = "card-link";
    link.href = item.url;
    const pic = document.createElement("div");
    pic.className = "pic";
    if (item.photo) {
      const img = document.createElement("img");
      img.src = item.photo;
      img.alt = item.name;
      img.loading = "lazy";
      pic.append(img);
    }
    const meta = document.createElement("div");
    meta.className = "meta";
    const name = document.createElement("div");
    name.className = "name";
    name.textContent = item.name;
    meta.append(name);
    link.append(pic, meta);

    const actions = document.createElement("div");
    actions.className = "card-actions";
    const cost = document.createElement("span");
    cost.className = "price";
    cost.textContent = price(item.price);

    const buttons = document.createElement("div");
    buttons.className = "card-buttons";
    // На странице избранного сердце избыточно: кнопка прямо убирает товар
    const fav = document.createElement("button");
    fav.className = "cart-drop";
    fav.type = "button";
    fav.textContent = "Убрать";
    fav.addEventListener("click", () => {
      remove("favorites", item.id);
      paint();
      renderCollections();
    });
    const cart = document.createElement("button");
    cart.className = "cart-btn";
    cart.type = "button";
    cart.dataset.toggle = "cart";
    cart.dataset.product = String(item.id);
    cart.dataset.labelOn = "В корзине";
    cart.textContent = "В корзину";
    buttons.append(fav, cart);
    actions.append(cost, buttons);

    card.append(link, actions);
    return card;
  };

  const showState = (kind, state) => {
    const empty = document.querySelector(`[data-collection-empty="${kind}"]`);
    const failed = document.querySelector(`[data-collection-error="${kind}"]`);
    if (empty) empty.hidden = state !== "empty";
    if (failed) failed.hidden = state !== "failed";
  };

  const renderCollection = async (mount) => {
    const kind = mount.dataset.collection;
    const ids = read(kind);
    mount.replaceChildren();
    if (!ids.length) {
      mount.hidden = true;
      showState(kind, "empty");
      return;
    }
    let items = [];
    let loaded = false;
    try {
      const response = await fetch(`/api/products?ids=${ids.join(",")}`, {
        headers: { Accept: "application/json" },
      });
      if (response.ok) {
        items = (await response.json()).items;
        loaded = true;
      }
    } catch {
      // Сеть отвалилась — подборку не трогаем и честно говорим об этом
    }
    if (!loaded) {
      // Пустое состояние здесь соврало бы: подборка цела, не загрузился ответ
      mount.hidden = true;
      showState(kind, "failed");
      return;
    }
    // Товар, снятый с публикации, из подборки уходит вместе с id
    write(
      kind,
      items.map((item) => item.id),
    );
    paintCounters();
    if (!items.length) {
      mount.hidden = true;
      showState(kind, "empty");
      return;
    }
    mount.hidden = false;
    showState(kind, "filled");
    const build = kind === "cart" ? cartRow : favoriteCard;
    items.forEach((item) => mount.append(build(item)));
    paintButtons(mount);
  };

  const renderCollections = () => {
    document.querySelectorAll("[data-collection]").forEach(renderCollection);
  };

  // ---------- Форма заявки ----------

  const NOTES = {
    consent: "Отметьте согласие на обработку персональных данных.",
    name: "Укажите имя — менеджеру нужно, как к вам обращаться.",
    phone: "Укажите телефон, по которому с вами можно связаться.",
    sent: "Спасибо! Мы свяжемся с вами в ближайшее время.",
    invalid: "Проверьте имя и телефон: заявку не удалось разобрать.",
    tooMany: "Слишком много заявок подряд — попробуйте позже или позвоните.",
    failed:
      "Не удалось отправить заявку — позвоните нам или напишите в мессенджер.",
  };

  // Сервер присылает разбор ошибки: {"detail": [{"msg": "…"}]}. Внятное
  // сообщение (истёкший CSRF, исчезнувший товар) показываем как есть —
  // оба случая лечатся обновлением страницы, а не звонком
  const serverNote = async (response) => {
    if (response.status === 429) return NOTES.tooMany;
    if (response.status === 400) return NOTES.invalid;
    try {
      const payload = await response.json();
      const message = payload?.detail?.[0]?.msg;
      if (typeof message === "string" && message) return message;
    } catch {
      // Ответ не JSON — остаётся общее сообщение
    }
    return NOTES.failed;
  };

  const formItems = (form) => {
    if (form.dataset.source === "cart") return read("cart");
    return form.dataset.product ? [Number(form.dataset.product)] : [];
  };

  const submit = async (form) => {
    const note = form.querySelector("[data-lead-note]");
    const button = form.querySelector("[type=submit]");
    const data = new FormData(form);
    if (!form.querySelector("[name=consent]").checked) {
      note.textContent = NOTES.consent;
      return;
    }
    // Те же требования, что и на сервере, но по обрезанным значениям:
    // иначе «a » проходит minlength в браузере и падает на эндпоинте
    const name = (data.get("name") || "").trim();
    const phone = (data.get("phone") || "").trim();
    if (name.length < 2) {
      note.textContent = NOTES.name;
      return;
    }
    if ((phone.match(/\d/g) || []).length < 7) {
      note.textContent = NOTES.phone;
      return;
    }
    button.disabled = true;
    try {
      const response = await fetch("/api/leads", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": data.get("csrfmiddlewaretoken") || "",
        },
        body: JSON.stringify({
          name,
          phone,
          email: (data.get("email") || "").trim(),
          comment: (data.get("comment") || "").trim(),
          source: form.dataset.source,
          consent: true,
          items: formItems(form),
        }),
      });
      if (!response.ok) {
        note.textContent = await serverNote(response);
        return;
      }
      note.textContent = NOTES.sent;
      form.reset();
      if (form.dataset.source === "cart") {
        write("cart", []);
        paint();
        renderCollections();
      }
    } catch {
      note.textContent = NOTES.failed;
    } finally {
      button.disabled = false;
    }
  };

  document.querySelectorAll("[data-lead-form]").forEach((form) => {
    form.addEventListener("submit", (event) => {
      event.preventDefault();
      submit(form);
    });
  });

  paint();
  renderCollections();
})();
