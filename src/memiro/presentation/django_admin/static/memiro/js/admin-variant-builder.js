// Конструктор предпосчитанных вариантов в карточке товара (ADR-0011).
// Владелец ставит размер, выбирает отличия от товара и сразу видит цену;
// поля после «Добавить» остаются заполненными — следующий вариант обычно
// отличается одним размером.
//
// Цену не считает: за ней ходит к серверу, тем же расчётом, что запишет её
// варианту. В режиме «вписать руками» не ходит вовсе — считать нечего, и
// записано будет ровно набранное число (ADR-0017). Ставок, коэффициентов и
// разбора изделия на статьи сюда не приезжает — как и на витрину (ADR-0007).
// Разбивку тысяч тоже присылает сервер: типографика цены у сайта одна.
//
// Запускается по `DOMContentLoaded`, а не сразу: медиа админки Django
// печатает этот тег в `<head>` и без `defer`, поэтому в момент выполнения
// разметки конструктора ещё нет — и панель молча осталась бы мёртвой.
document.addEventListener("DOMContentLoaded", () => {
  // Панель, а не форма: Django печатает этот блок внутри формы товара, а
  // вложенную форму браузер выбрасывает целиком. Токен CSRF берётся у формы
  // товара — своего у панели быть не может
  const panel = document.getElementById("variant-builder-form");
  if (!panel) return;

  const table = document.querySelector("#variant-rows tbody");
  const empty = document.getElementById("variant-empty");
  const price = document.getElementById("variant-price");
  const apply = document.getElementById("variant-add");
  const cancel = document.getElementById("variant-cancel");
  const width = document.getElementById("variant-width");
  const height = document.getElementById("variant-height");
  const order = document.getElementById("variant-order");
  const edited = document.getElementById("variant-edited");
  const mode = document.getElementById("variant-mode");
  const priceSource = document.getElementById("variant-price-source");
  const manual = document.getElementById("variant-manual-price");
  const token = document.querySelector('input[name="csrfmiddlewaretoken"]');

  const NOTES = {
    sizes: "Введите ширину и высоту — посчитаем цену варианта.",
    counting: "Считаем цену…",
    failed: "Не удалось посчитать цену. Попробуйте ещё раз.",
    // Истёкшая сессия отвечает не отказом, а страницей входа: сервер уводит
    // на неё редиректом, и разбор JSON спотыкается об HTML. Без этой строки
    // владелец прочитал бы английское сообщение разборщика браузера
    expired: "Сессия админки истекла — войдите заново и повторите.",
    price: "Впишите цену варианта в рублях.",
    manual: "Цена вписана руками — пересчёт каталога её не тронет.",
  };
  const LABELS = { add: "Добавить", edit: "Сохранить", clone: "Размножить" };

  // Ответ, пришедший не JSON-ом, — это не ответ конструктора
  const answered = async (response) => {
    try {
      return await response.json();
    } catch {
      return { error: response.ok ? NOTES.failed : NOTES.expired };
    }
  };

  const say = (text, failed) => {
    price.textContent = text;
    price.classList.toggle("variant-price-failed", Boolean(failed));
  };

  // Имён у полей панели нет: с ними они уезжали бы на сервер вместе с
  // карточкой товара. Что чем является, говорит разметка
  const controls = () => [
    ...panel.querySelectorAll("[data-variant-attribute]"),
  ];

  // Что сейчас стоит в полях. Пусто, пока размеры не введены: своего размера
  // у товара нет, и до них считать нечего
  const composed = () => {
    const data = new URLSearchParams();
    if (!(Number(width.value) > 0 && Number(height.value) > 0)) return null;
    data.set("width_mm", width.value);
    data.set("height_mm", height.value);
    data.set("sort_order", order.value || "0");
    if (handwritten()) data.set("manual_price", manual.value);
    controls().forEach((control) => {
      if (!control.value) return;
      const named = control.hasAttribute("data-variant-quantity")
        ? "quantity"
        : "value";
      data.append(named, `${control.dataset.variantAttribute}:${control.value}`);
    });
    return data;
  };

  // Вписанная цена — это режим, а не заполненность поля: правя посчитанный
  // вариант, владелец не должен нечаянно зафиксировать его цену руками
  const handwritten = () => priceSource.value === "manual";

  const send = async (url, data) => {
    const response = await fetch(url, {
      method: "POST",
      headers: { Accept: "application/json", "X-CSRFToken": token.value },
      body: data,
    });
    const answer = await answered(response);
    if (!response.ok || !answer.variants) {
      throw new Error(answer.error || NOTES.failed);
    }
    return answer;
  };

  // Ответы приходят не в порядке отправки: показываем только последний
  // запрошенный, иначе цена мигала бы на предыдущий размер
  let latest = 0;
  // Идёт ли сейчас запись. Пока идёт, вторая кнопка не нажимается: список
  // перерисовывается ответом целиком, и ответ, пришедший вторым, вернул бы
  // владельцу состояние до первой правки
  let writing = false;

  // Кнопка ждёт цену. Ввод миллиметров дебаунсится, и всё это время на
  // экране висит цена прежнего размера — нажав «Добавить» тогда, владелец
  // завёл бы вариант, глядя на чужое число
  const settled = (ready) => {
    apply.disabled = !ready || writing;
  };

  const recalculate = async () => {
    const ticket = ++latest;
    const data = composed();
    if (!data) {
      say(NOTES.sizes);
      settled(false);
      return;
    }
    if (handwritten()) {
      const written = manual.value !== "" && Number(manual.value) >= 0;
      say(written ? NOTES.manual : NOTES.price, !written);
      settled(written);
      return;
    }
    let quote = null;
    try {
      const response = await fetch(`${panel.dataset.priceUrl}?${data}`, {
        headers: { Accept: "application/json" },
      });
      const answer = await answered(response);
      quote = response.ok ? answer : { error: answer.error || NOTES.failed };
    } catch {
      quote = { error: NOTES.failed };
    }
    if (ticket !== latest) return;
    if (quote.error) say(quote.error, true);
    else say(quote.price_label);
    settled(!quote.error);
  };

  // Поля тронули — показанная цена устарела в тот же миг, задолго до ответа
  // сервера. Говорим об этом сразу, а не молчим 400 мс
  const staled = () => {
    say(composed() ? NOTES.counting : NOTES.sizes);
    settled(false);
  };

  const row = (variant) => {
    const line = document.createElement("tr");
    const cell = (text) => {
      const td = document.createElement("td");
      td.textContent = text;
      line.append(td);
      return td;
    };
    cell(variant.sort_order);
    cell(variant.size_label);
    cell(variant.values_label);
    const money = cell(variant.price_label);
    if (variant.price_is_manual) {
      const mark = document.createElement("span");
      mark.className = "variant-manual";
      mark.textContent = " — вписана руками";
      money.append(mark);
    }
    if (variant.sets_product_price) {
      const mark = document.createElement("span");
      mark.className = "variant-cheapest";
      mark.textContent = " — отсюда «от» на витрине";
      money.append(mark);
    }
    const actions = cell("");
    [
      ["Править", "edit"],
      ["Размножить размером", "clone"],
      ["Удалить", "delete"],
    ].forEach(([label, action]) => {
      const button = document.createElement("button");
      button.type = "button";
      button.textContent = label;
      button.dataset.action = action;
      button.dataset.variant = variant.variant_id;
      actions.append(button);
    });
    return line;
  };

  // Список перерисовывается целиком: «от» на витрине даёт самый дешёвый
  // вариант, и заведённый вариант меняет пометку у другого
  let rows = [];
  const redraw = (variants) => {
    rows = variants;
    table.replaceChildren(...variants.map(row));
    // Шапка без единой строки под ней обещает список, которого нет
    table.closest("table").hidden = variants.length === 0;
    empty.hidden = variants.length > 0;
  };

  const fill = (variant) => {
    width.value = variant.width_mm;
    height.value = variant.height_mm;
    order.value = variant.sort_order;
    priceSource.value = variant.price_is_manual ? "manual" : "calculated";
    manual.value = variant.manual_price;
    priced();
    controls().forEach((control) => {
      control.value = variant.overrides[control.dataset.variantAttribute] || "";
    });
  };

  // Правка и размножение отличаются от заведения одним: у них есть исходный
  // вариант. Кнопка называет то, что случится, — иначе «Добавить» посреди
  // правки завело бы владельцу лишний вариант.
  //
  // Размножение берёт с панели только размер: отличия и порядок копия
  // наследует от исходного варианта. Поэтому в этом режиме они заперты —
  // иначе владелец правил бы поля, глядя на цену, которая запишется, и
  // получал бы вариант, этой правки не знающий
  const editing = (variant, action) => {
    edited.value = variant ? variant.variant_id : "";
    mode.value = variant ? action : "";
    apply.textContent = variant ? LABELS[action] : LABELS.add;
    cancel.hidden = !variant;
    const inherited = mode.value === "clone";
    order.disabled = inherited;
    priceSource.disabled = inherited;
    manual.disabled = inherited || !handwritten();
    controls().forEach((control) => {
      control.disabled = inherited;
    });
  };

  // Поле цены живёт ровно в своём режиме: открытое в режиме расчёта, оно
  // обещало бы владельцу число, которого никто не запишет
  const priced = () => {
    manual.disabled = !handwritten();
  };

  const found = (id) =>
    rows.find((variant) => String(variant.variant_id) === id);

  const failed = (error) => say(error.message || NOTES.failed, true);

  apply.addEventListener("click", async () => {
    const data = composed();
    if (!data) {
      say(NOTES.sizes, true);
      return;
    }
    const source = edited.value;
    if (source) data.set("variant", source);
    if (mode.value === "clone") data.set("duplicate", "1");
    writing = true;
    apply.disabled = true;
    try {
      redraw((await send(panel.dataset.saveUrl, data)).variants);
      // Поля остаются заполненными: следующий вариант отличается обычно
      // одним размером. Правка при этом из правки не выходит — иначе
      // следующий щелчок по той же кнопке, ничего не изменив, завёл бы
      // дубль только что переписанного варианта
      if (mode.value !== "edit") editing(null);
    } catch (error) {
      failed(error);
    } finally {
      writing = false;
      recalculate();
    }
  });

  cancel.addEventListener("click", () => {
    editing(null);
    recalculate();
  });

  table.addEventListener("click", async (event) => {
    const button = event.target.closest("button[data-action]");
    if (!button) return;
    const variant = found(button.dataset.variant);
    if (!variant) return;
    if (button.dataset.action === "edit") {
      fill(variant);
      editing(variant, "edit");
      recalculate();
      width.focus();
      return;
    }
    if (button.dataset.action === "clone") {
      // Копия, у которой меняется только размер: отличия остаются
      // выбранными, курсор встаёт в ширину — по опыту владельца это
      // половина всей работы. Размножает сервер, командой агрегата, и
      // порядок копия наследует от исходного варианта
      fill(variant);
      editing(variant, "clone");
      recalculate();
      width.select();
      return;
    }
    if (writing) return;
    if (!window.confirm(`Удалить вариант ${variant.size_label}?`)) return;
    const data = new URLSearchParams({ variant: variant.variant_id });
    writing = true;
    try {
      redraw((await send(panel.dataset.deleteUrl, data)).variants);
      if (edited.value === String(variant.variant_id)) editing(null);
    } catch (error) {
      failed(error);
    } finally {
      writing = false;
      recalculate();
    }
  });

  // Ввод миллиметров идёт посимвольно: 1900 по пути через 1, 19 и 190
  let typing = null;
  [width, height].forEach((field) => {
    field.addEventListener("input", () => {
      staled();
      clearTimeout(typing);
      typing = setTimeout(recalculate, 400);
    });
    field.addEventListener("change", recalculate);
  });
  panel.addEventListener("change", (event) => {
    if (event.target.matches("[data-variant-attribute]")) recalculate();
  });
  priceSource.addEventListener("change", () => {
    priced();
    recalculate();
  });
  manual.addEventListener("input", recalculate);

  redraw(JSON.parse(document.getElementById("variant-rows-data").textContent));
  priced();
  recalculate();
});
