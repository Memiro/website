// Избранное, корзина и отправка заявки (тикет 07).
// Подборки живут в localStorage: регистрации нет, сервер о них не знает.
// Названия и цены всегда берутся с сервера — цена остаётся его правдой.
(() => {
  const KEYS = {
    cart: "memiro:cart",
    favorites: "memiro:favorites",
  };
  // Границы приходят с сервера (memiro/inquiries/limits.py): вторая
  // копия чисел разъехалась бы с валидацией эндпоинтов
  const limits = (() => {
    const blob = document.getElementById("inquiry-limits");
    try {
      return JSON.parse(blob.textContent);
    } catch {
      return { max_items: 100, min_phone_digits: 7 };
    }
  })();

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
    // Потолок тот же, что у эндпоинтов: длинный список они отвергнут
    if (ids.length >= limits.max_items) {
      announce(`Больше ${limits.max_items} товаров в подборку не помещается.`);
      return false;
    }
    write(kind, [...ids, id]);
    return true;
  };

  // Живая область под сообщения, которым негде показаться в разметке
  let noteTimer = null;
  const announce = (text) => {
    const note = document.querySelector("[data-shop-note]");
    if (!note) return;
    note.textContent = text;
    note.hidden = false;
    clearTimeout(noteTimer);
    noteTimer = setTimeout(() => {
      note.hidden = true;
    }, 5000);
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
    // Подписи живут в разметке: JS их не сочиняет, а читает
    const label = isOn ? button.dataset.labelOn : button.dataset.labelOff;
    button.setAttribute("aria-pressed", String(isOn));
    button.classList.toggle("on", isOn);
    if (!label) return;
    // У иконочных кнопок текста нет — правим только подпись для чтеца,
    // иначе textContent затёр бы вложенный SVG
    const text = [...button.childNodes].find(
      (node) => node.nodeType === Node.TEXT_NODE && node.textContent.trim(),
    );
    if (text) text.textContent = ` ${label}`;
    button.setAttribute("aria-label", label);
    button.title = label;
  };

  const paintButtons = (root = document) => {
    root.querySelectorAll("[data-toggle][data-product]").forEach(paintButton);
  };

  const paint = () => {
    paintCounters();
    paintButtons();
    paintCartNotes();
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

  const price = (value) => `от ${window.memiro.rub(value)} ₽`;

  // Пропущенные узлы отсеиваются на сборке, а не у каждого append
  const present = (...nodes) => nodes.filter(Boolean);

  // null — товару не завели предпосчитанных вариантов, цены нет вовсе
  // (ADR-0007). Шаблоны в таком случае не печатают и самого элемента —
  // здесь так же, иначе разметка карточек разойдётся с серверной
  const priceNode = (value, tag, className) => {
    if (value == null) return null;
    const node = document.createElement(tag);
    node.className = className;
    node.textContent = price(value);
    return node;
  };

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

    const cost = priceNode(item.price, "div", "cart-price");

    const drop = document.createElement("button");
    drop.className = "cart-drop";
    drop.type = "button";
    drop.textContent = "Убрать";
    drop.addEventListener("click", () => {
      remove("cart", item.id);
      paint();
      renderCollections();
    });

    row.append(...present(link, meta, cost, drop));
    return row;
  };

  // Зеркало шаблона catalog/_card.html: разметку карточки правим в обоих
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
    const cost = priceNode(item.price, "span", "price");

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
    cart.dataset.labelOff = "В корзину";
    cart.dataset.labelOn = "В корзине";
    cart.textContent = "В корзину";
    buttons.append(fav, cart);
    actions.append(...present(cost, buttons));

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
    failed:
      "Не удалось отправить заявку — позвоните нам или напишите в мессенджер.",
  };

  // Сервер присылает разбор ошибки: {"detail": [{"msg": "…"}]}. Внятное
  // сообщение (истёкший CSRF, исчезнувший товар) показываем как есть —
  // оба случая лечатся обновлением страницы, а не звонком
  const serverNote = async (response) => {
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

  const cartForm = (form) => form.dataset.source !== "product";

  const formItems = (form) => {
    if (cartForm(form)) return read("cart");
    return form.dataset.product ? [Number(form.dataset.product)] : [];
  };

  // «товар / товара / товаров» — как фильтр ru_plural в шаблонах
  const products = (count) => {
    const tail = count % 10;
    const teens = count % 100;
    if (teens >= 11 && teens <= 14) return "товаров";
    if (tail === 1) return "товар";
    if (tail >= 2 && tail <= 4) return "товара";
    return "товаров";
  };

  // Посетитель должен видеть, что к заявке уедет собранная подборка
  const paintCartNote = (form) => {
    const note = form.querySelector("[data-inquiry-cart-note]");
    if (!note) return;
    const count = cartForm(form) ? read("cart").length : 0;
    // На странице корзины состав и так перед глазами
    const silent = form.dataset.source === "cart";
    note.hidden = !count || silent;
    note.textContent = count
      ? `К заявке приложим вашу подборку: ${count} ${products(count)}.`
      : "";
  };

  const paintCartNotes = () => {
    document.querySelectorAll("[data-inquiry-form]").forEach(paintCartNote);
  };

  const submit = async (form) => {
    const note = form.querySelector("[data-inquiry-note]");
    const say = (text, ok = false) => {
      note.textContent = text;
      note.classList.toggle("error", !ok);
    };
    const button = form.querySelector("[type=submit]");
    const data = new FormData(form);
    if (!form.querySelector("[name=consent]").checked) {
      say(NOTES.consent);
      return;
    }
    // Те же требования, что и на сервере, но по обрезанным значениям:
    // иначе «a » проходит minlength в браузере и падает на эндпоинте
    const name = (data.get("name") || "").trim();
    const phone = (data.get("phone") || "").trim();
    if (name.length < 2) {
      say(NOTES.name);
      return;
    }
    if ((phone.match(/\d/g) || []).length < limits.min_phone_digits) {
      say(NOTES.phone);
      return;
    }
    button.disabled = true;
    try {
      const response = await fetch("/api/inquiries", {
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
        say(await serverNote(response));
        return;
      }
      say(NOTES.sent, true);
      form.reset();
      if (cartForm(form) && read("cart").length) {
        // Подборка ушла менеджеру — держать её дальше незачем
        write("cart", []);
        paint();
        renderCollections();
      }
    } catch {
      say(NOTES.failed);
    } finally {
      button.disabled = false;
    }
  };

  document.querySelectorAll("[data-inquiry-form]").forEach((form) => {
    form.addEventListener("submit", (event) => {
      event.preventDefault();
      submit(form);
    });
  });

  paint();
  renderCollections();
})();
