// Подборка и отправка заявки (тикет 07).
// На витрине она называется заявкой (тикет 13); `cart` осталось
// внутренним именем — так её зовут разметка, хранилище и модель.
// Подборка живёт в localStorage: регистрации нет, сервер о ней не знает.
// Хранит она не список id, а позиции — товар и то, каким его настроили
// на карточке: заявка из двух зеркал разных размеров иначе запомнила бы
// одно (тикет 14, ADR-0009). Вместе с зеркалом лежит и личное пожелание
// к нему — свободный текст, который в расчёт не идёт (тикет 15).
// Названия и цены всегда берутся с сервера — цена остаётся его правдой.
// Вид подборки (`kind`) ездит параметром не про запас, а потому что
// приходит из разметки: `data-toggle`, `data-count`, `data-collection`.
(() => {
  const KEYS = {
    cart: "memiro:cart",
  };
  // Имя события калькулятора — то же, что шлёт product.js
  const CONFIGURED = "memiro:configured";
  // Границы приходят с сервера (memiro/inquiries/limits.py): вторая
  // копия чисел разъехалась бы с валидацией эндпоинтов
  const limits = (() => {
    const blob = document.getElementById("inquiry-limits");
    try {
      return JSON.parse(blob.textContent);
    } catch {
      return { max_items: 100, min_phone_digits: 7, max_wish_length: 500 };
    }
  })();

  // Конфигурация из хранилища: чужому объекту здесь взяться неоткуда,
  // но испорченное хранилище не повод отправить менеджеру мусор
  const configuration = (value) => {
    if (!value) return null;
    const { width_mm, height_mm, values } = value;
    if (!(width_mm > 0 && height_mm > 0)) return null;
    return {
      width_mm,
      height_mm,
      values: Array.isArray(values) ? values.filter(Number.isInteger) : [],
    };
  };

  // Личное пожелание к зеркалу: свободный текст покупателя, в расчёт
  // он не идёт (тикет 15). Обрезается тем же потолком, что у эндпоинта:
  // длинное пожелание отвергло бы всю заявку вместе с контактами
  // Режется по символам, а не по единицам UTF-16: `slice` разрубил бы
  // эмодзи пополам, оставив половину суррогатной пары, и считал бы её
  // за два. Сервер считает символы — на потолке эти двое должны
  // сходиться, иначе заявку отвергнет то, что браузер пропустил
  const trimmedWish = (value) =>
    typeof value === "string"
      ? [...value.trim()].slice(0, limits.max_wish_length).join("")
      : "";

  // Позиция подборки — товар и то, каким его настроили на карточке:
  // габариты и выбранные значения (тикет 14, ADR-0009). Цены здесь
  // нет: её называет сервер, пересчитывая конфигурацию теми же
  // тарифами, что и витрина. Число из браузера доказательством
  // в споре о цене не было бы
  const entry = (value) => {
    // Подборка, сложенная до переезда, — просто список id. Своей
    // конфигурации у неё не было, и выдумывать её нечем
    if (Number.isInteger(value))
      return { product: value, configuration: null, wish: "" };
    if (!value || !Number.isInteger(value.product)) return null;
    return {
      product: value.product,
      configuration: configuration(value.configuration),
      wish: trimmedWish(value.wish),
    };
  };

  const read = (kind) => {
    try {
      const stored = JSON.parse(localStorage.getItem(KEYS[kind]) || "[]");
      return Array.isArray(stored) ? stored.map(entry).filter(Boolean) : [];
    } catch {
      // Испорченное хранилище — не повод ронять страницу
      return [];
    }
  };

  // Товары подборки: их спрашивают у /api/products и ими же красят
  // кнопки. Позиция помнит больше, но здесь нужен только товар
  const productIds = (kind) => read(kind).map((item) => item.product);

  const write = (kind, items) => {
    try {
      localStorage.setItem(KEYS[kind], JSON.stringify(items));
    } catch {
      // Приватный режим без записи: подборка живёт до перезагрузки
    }
  };

  const toggle = (kind, id, configured, said) => {
    const items = read(kind);
    if (items.some((item) => item.product === id)) {
      write(
        kind,
        items.filter((item) => item.product !== id),
      );
      return false;
    }
    // Потолок тот же, что у эндпоинтов: длинный список они отвергнут
    if (items.length >= limits.max_items) {
      announce(`Больше ${limits.max_items} товаров в заявку не помещается.`);
      return false;
    }
    write(kind, [
      ...items,
      { product: id, configuration: configured, wish: said },
    ]);
    return true;
  };

  // ---------- Личное пожелание ----------

  // Пожелание правится у уже собранного зеркала: покупатель дописывает
  // его на карточке после нажатия и на странице заявки, передумав
  // (тикет 15). Позиции нет в подборке — писать некуда, и это не
  // потеря: пожелание уедет вместе с зеркалом, когда его добавят.
  //
  // Подборка здесь названа прямо, а не приехала параметром `kind`:
  // поле пожелания живёт в разметке само по себе, и вида подборки
  // при нём нет. Заведись вторая — `data-wish` назовёт её так же,
  // как `data-toggle` называет её кнопке
  const rememberWish = (id, said) => {
    const items = read("cart");
    if (!items.some((item) => item.product === id && item.wish !== said)) {
      return;
    }
    write(
      "cart",
      items.map((item) =>
        item.product === id ? { ...item, wish: said } : item,
      ),
    );
  };

  // Поле пожелания карточки — своё у каждого товара: `data-wish`
  // назван товаром по той же причине, что и событие калькулятора
  const wishField = (id) => document.querySelector(`[data-wish="${id}"]`);

  document.addEventListener("input", (event) => {
    const field = event.target.closest("[data-wish]");
    if (!field) return;
    rememberWish(Number(field.dataset.wish), trimmedWish(field.value));
  });

  // Что покупатель написал в прошлый раз: подборка переживает
  // перезагрузку, и пожелание должно пережить её вместе с зеркалом
  const paintWishes = () => {
    read("cart").forEach((item) => {
      const field = wishField(item.product);
      // Набранное сейчас не затираем: поле правит покупатель, а не мы
      if (field && !field.value) field.value = item.wish;
    });
  };

  // ---------- Что объявил калькулятор карточки ----------

  // Калькулятор живёт в product.js и сам говорит, что покупатель
  // настроил: событием, а не общей функцией. У события есть свой
  // товар, и вторая кнопка «Добавить в заявку» на той же странице
  // чужих размеров не подхватит. Второй разбор тех же полей здесь
  // однажды разошёлся бы с первым — потому слушаем, а не читаем.
  // Последнее объявленное по каждому товару: кнопка нажимается
  // когда угодно, а поля к тому времени давно набраны
  const latest = new Map();

  const same = (one, other) => JSON.stringify(one) === JSON.stringify(other);

  document.addEventListener(CONFIGURED, (event) => {
    const { product, configuration: sent } = event.detail;
    latest.set(product, sent);
    const items = read("cart");
    // Зеркало уже в подборке: менеджеру оно должно уехать таким,
    // каким покупатель видит его сейчас, а не каким добавил. Иначе
    // передумавший о размере получил бы не то, что заказывал.
    // Ничего не поменялось — не пишем: калькулятор объявляет
    // конфигурацию на каждый пересчёт, в том числе на тот же размер
    if (
      !items.some(
        (item) => item.product === product && !same(item.configuration, sent),
      )
    ) {
      return;
    }
    write(
      "cart",
      items.map((item) =>
        item.product === product ? { ...item, configuration: sent } : item,
      ),
    );
  });

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
      read(kind).filter((item) => item.product !== id),
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
    const isOn = productIds(kind).includes(Number(button.dataset.product));
    button.setAttribute("aria-pressed", String(isOn));
    button.classList.toggle("on", isOn);
    // Подписи живут в разметке: JS их не сочиняет, а читает. Подпись же
    // и служит кнопке именем для чтеца — второго имени в `aria-label`
    // быть не должно, оно бы с ней разошлось
    button.textContent = isOn
      ? button.dataset.labelOn
      : button.dataset.labelOff;
  };

  const paintButtons = () => {
    document
      .querySelectorAll("[data-toggle][data-product]")
      .forEach(paintButton);
  };

  const paint = () => {
    paintCounters();
    paintButtons();
    paintWishes();
    paintCartNotes();
  };

  document.addEventListener("click", (event) => {
    const button = event.target.closest("[data-toggle][data-product]");
    if (!button) return;
    event.preventDefault();
    const id = Number(button.dataset.product);
    // Настроенное на карточке едет в подборку вместе с зеркалом
    // (тикет 14). Товару без калькулятора конфигурации взять неоткуда.
    // Пожелание же читается прямо из поля рядом: набрано оно к этому
    // нажатию, а не к событию калькулятора (тикет 15)
    const field = wishField(id);
    toggle(
      button.dataset.toggle,
      id,
      latest.get(id) ?? null,
      field ? trimmedWish(field.value) : "",
    );
    paint();
  });

  // Подборка могла измениться в соседней вкладке
  window.addEventListener("storage", () => {
    paint();
    renderCollections();
  });

  // ---------- Строки подборки ----------

  const price = (value) => `от ${window.memiro.rub(value)} ₽`;

  // null — товару не завели предпосчитанных вариантов, цены нет вовсе
  // (ADR-0007). Заглушку на её месте не ставим и здесь: пустая ячейка
  // строки честнее «уточняйте», а колонку «Убрать» держит `grid-column`
  const priceNode = (value) => {
    if (value == null) return null;
    const node = document.createElement("div");
    node.className = "cart-price";
    node.textContent = price(value);
    return node;
  };

  // Пожелание правится там же, где покупатель видит своё зеркало:
  // передумавший о втором выключателе иначе снимал бы зеркало и
  // добавлял его заново (тикет 15). Текст ставится значением поля,
  // а не разметкой: чужих тегов в подборке взяться неоткуда, но
  // печатать хранилище разметкой — не то обещание, что стоит давать
  const wishRow = (item) => {
    const label = document.createElement("label");
    // `field` — тот же вид, что у полей формы заявки рядом: одно
    // поле на сайте выглядит одинаково, где бы оно ни стояло
    label.className = "field wish-field";
    const caption = document.createElement("span");
    caption.textContent = "Пожелание";
    const field = document.createElement("textarea");
    field.rows = 2;
    field.maxLength = limits.max_wish_length;
    field.dataset.wish = String(item.id);
    // Чтецу зеркало называется в самом имени поля: подписей «Пожелание»
    // на странице столько же, сколько зеркал, и глазами их различает
    // название строкой выше, а на слух — ничто. Видимая подпись входит
    // в это имя целиком, иначе они разошлись бы у тех, кто читает
    // экран и слушает его одновременно
    field.setAttribute(
      "aria-label",
      `${caption.textContent} к зеркалу «${item.name}»`,
    );
    // Подсказки здесь нет намеренно: пример уже стоял в поле карточки,
    // а вторая его копия — второй текст, который однажды разойдётся
    // с первым. Строка правится у зеркала, названного прямо над ней.
    // Написанного поле тоже не несёт: его ставит `paintWishes` — одно
    // место читает хранилище и для карточки, и для строки
    label.append(caption, field);
    return label;
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
    meta.append(title, category, wishRow(item));

    const cost = priceNode(item.price);

    const drop = document.createElement("button");
    drop.className = "cart-drop";
    drop.type = "button";
    drop.textContent = "Убрать";
    drop.addEventListener("click", () => {
      remove("cart", item.id);
      paint();
      renderCollections();
    });

    // Цены может не быть — тогда её ячейка просто пустует
    row.append(...[link, meta, cost, drop].filter(Boolean));
    return row;
  };

  const showState = (kind, state) => {
    const empty = document.querySelector(`[data-collection-empty="${kind}"]`);
    const failed = document.querySelector(`[data-collection-error="${kind}"]`);
    if (empty) empty.hidden = state !== "empty";
    if (failed) failed.hidden = state !== "failed";
  };

  const renderCollection = async (mount) => {
    const kind = mount.dataset.collection;
    const ids = productIds(kind);
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
    // Товар, снятый с публикации, уходит из подборки вместе со своей
    // позицией; у остальных конфигурация остаётся нетронутой
    const alive = new Set(items.map((item) => item.id));
    write(
      kind,
      read(kind).filter((item) => alive.has(item.product)),
    );
    paintCounters();
    if (!items.length) {
      mount.hidden = true;
      showState(kind, "empty");
      return;
    }
    mount.hidden = false;
    showState(kind, "filled");
    items.forEach((item) => mount.append(cartRow(item)));
    // Строки готовы — написанное покупателем ставит в них то же место,
    // что и на карточке товара: второй чтец хранилища разошёлся бы
    // с первым на первой же правке
    paintWishes();
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
    const count = read("cart").length;
    // На странице заявки состав и так перед глазами
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
          // Формы на карточке товара больше нет (тикет 07), и всякая
          // оставшаяся форма отправляет одно и то же — собранную
          // подборку: своего товара ни у одной из них нет. Конфигурация
          // едет от позиции подборки, а не от формы (тикет 14,
          // ADR-0009), и цену на неё называет сервер
          items: read("cart"),
        }),
      });
      if (!response.ok) {
        say(await serverNote(response));
        return;
      }
      say(NOTES.sent, true);
      form.reset();
      if (read("cart").length) {
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
