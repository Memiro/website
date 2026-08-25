// Конструктор предпосчитанных вариантов в карточке товара (тикет 18).
// Владелец ставит размер, отмечает значения и сразу видит цену; поля
// после «Добавить» остаются заполненными — следующий вариант обычно
// отличается одним размером.
//
// Цену не считает: за ней ходит к серверу, тем же расчётом, что
// запишет её варианту (`catalog.variants`). Ставок, коэффициентов и
// разбора изделия на статьи сюда не приезжает — как и на витрину
// (ADR-0007). Разбивку тысяч тоже присылает сервер: типографика цены
// у сайта одна.
(() => {
  // Панель, а не форма: Django печатает этот блок внутри формы
  // товара, а вложенную форму браузер выбрасывает целиком. Токен
  // CSRF берётся у формы товара — своего у панели быть не может
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
  const token = document.querySelector('input[name="csrfmiddlewaretoken"]');

  const NOTES = {
    sizes: "Введите ширину и высоту — посчитаем цену варианта.",
    failed: "Не удалось посчитать цену. Попробуйте ещё раз.",
  };

  const say = (text, failed) => {
    price.textContent = text;
    price.classList.toggle("variant-price-failed", Boolean(failed));
  };

  // Имён у полей панели нет: с ними они уезжали бы на сервер вместе
  // с карточкой товара. Что чем является, говорит разметка
  const checkboxes = () => [
    ...panel.querySelectorAll("input[data-variant-value]"),
  ];

  // Что сейчас стоит в полях. Пусто, пока размеры не введены: своего
  // размера у товара нет, и до них считать нечего
  const composed = () => {
    const data = new URLSearchParams();
    if (!(Number(width.value) > 0 && Number(height.value) > 0)) return null;
    data.set("width_mm", width.value);
    data.set("height_mm", height.value);
    data.set("order", order.value || "0");
    checkboxes()
      .filter((box) => box.checked)
      .forEach((box) => data.append("values", box.value));
    return data;
  };

  const send = async (url, data) => {
    const response = await fetch(url, {
      method: "POST",
      headers: {
        Accept: "application/json",
        "X-CSRFToken": token.value,
      },
      body: data,
    });
    const answer = await response.json();
    if (!response.ok) throw new Error(answer.error || NOTES.failed);
    return answer;
  };

  // Ответы приходят не в порядке отправки: показываем только последний
  // запрошенный, иначе цена мигала бы на предыдущий размер
  let latest = 0;

  const recalculate = async () => {
    const ticket = ++latest;
    const data = composed();
    if (!data) {
      say(NOTES.sizes);
      return;
    }
    let quote = null;
    try {
      const response = await fetch(`${panel.dataset.priceUrl}?${data}`, {
        headers: { Accept: "application/json" },
      });
      const answer = await response.json();
      quote = response.ok ? answer : { error: answer.error };
    } catch {
      quote = { error: NOTES.failed };
    }
    if (ticket !== latest) return;
    if (quote.error) say(quote.error, true);
    else say(quote.price_label);
  };

  const row = (variant) => {
    const line = document.createElement("tr");
    const cell = (text) => {
      const td = document.createElement("td");
      td.textContent = text;
      line.append(td);
      return td;
    };
    cell(variant.order);
    cell(variant.size_label);
    cell(variant.values_label);
    const money = cell(variant.price_label);
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

  // Список перерисовывается целиком: «от» на витрине даёт самый
  // дешёвый вариант, и заведённый вариант меняет пометку у другого
  let rows = [];
  const redraw = (variants) => {
    rows = variants;
    table.replaceChildren(...variants.map(row));
    empty.hidden = variants.length > 0;
  };

  const fill = (variant) => {
    width.value = variant.width_mm;
    height.value = variant.height_mm;
    order.value = variant.order;
    const chosen = new Set(variant.value_ids);
    checkboxes().forEach((box) => {
      box.checked = chosen.has(Number(box.value));
    });
  };

  // Правка отличается от заведения одним: у неё есть, что переписать.
  // Кнопка называет то, что случится, — иначе «Добавить» посреди
  // правки завело бы владельцу лишний вариант
  const editing = (variant) => {
    edited.value = variant ? variant.variant_id : "";
    apply.textContent = variant ? "Сохранить" : "Добавить";
    cancel.hidden = !variant;
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
    if (edited.value) data.set("variant", edited.value);
    apply.disabled = true;
    try {
      redraw((await send(panel.dataset.saveUrl, data)).variants);
      // Поля остаются заполненными: следующий вариант отличается
      // обычно одним размером — и правка на этом заканчивается
      editing(null);
      recalculate();
    } catch (error) {
      failed(error);
    } finally {
      apply.disabled = false;
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
      editing(variant);
      recalculate();
      width.focus();
      return;
    }
    if (button.dataset.action === "clone") {
      // Копия, у которой меняется только размер: значения остаются
      // отмеченными, курсор встаёт в ширину — по опыту владельца это
      // половина всей работы
      fill(variant);
      editing(null);
      recalculate();
      width.select();
      return;
    }
    if (!window.confirm(`Удалить вариант ${variant.size_label}?`)) return;
    const data = new URLSearchParams({ variant: variant.variant_id });
    try {
      redraw((await send(panel.dataset.deleteUrl, data)).variants);
      if (edited.value === String(variant.variant_id)) editing(null);
    } catch (error) {
      failed(error);
    }
  });

  // Ввод миллиметров идёт посимвольно: 1900 по пути через 1, 19 и 190
  let typing = null;
  [width, height].forEach((field) => {
    field.addEventListener("input", () => {
      clearTimeout(typing);
      typing = setTimeout(recalculate, 400);
    });
    field.addEventListener("change", recalculate);
  });
  panel.addEventListener("change", (event) => {
    if (event.target.matches("input[data-variant-value]")) recalculate();
  });

  redraw(JSON.parse(document.getElementById("variant-rows-data").textContent));
  recalculate();
})();
