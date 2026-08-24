// Галерея карточки товара: переключение главного кадра по миниатюрам
(() => {
  const main = document.querySelector("[data-gallery-main]");
  const thumbs = document.querySelectorAll(".thumbs button");
  if (!main || !thumbs.length) return;
  thumbs.forEach((thumb) => {
    thumb.addEventListener("click", () => {
      thumbs.forEach((other) => {
        other.classList.remove("on");
        other.setAttribute("aria-pressed", "false");
      });
      thumb.classList.add("on");
      thumb.setAttribute("aria-pressed", "true");
      main.src = thumb.dataset.src;
    });
  });
})();

// Калькулятор карточки (тикет 20): размеры и меняемые атрибуты →
// цена с /api/price. Ставки, коэффициенты и разбор изделия на статьи
// сюда не приезжают — считает сервер, браузер только показывает
// (ADR-0007). Блока в разметке нет у товара вне считаемого набора,
// и тогда весь этот код молчит.
(() => {
  const root = document.querySelector("[data-calc]");
  if (!root) return;
  const result = root.querySelector("[data-calc-result]");
  const width = root.querySelector("[data-calc-width]");
  const height = root.querySelector("[data-calc-height]");
  const selects = [...root.querySelectorAll("[data-calc-value]")];

  const NOTES = {
    sizes: "Введите ширину и высоту — посчитаем цену вашего размера.",
    inquiry:
      "Такой размер мы считаем индивидуально — оставьте заявку, " +
      "и менеджер назовёт цену.",
    failed: "Не удалось посчитать цену — попробуйте ещё раз или оставьте заявку.",
  };

  const note = (text) => {
    const paragraph = document.createElement("p");
    paragraph.className = "calc-note";
    paragraph.textContent = text;
    return paragraph;
  };

  // Просто сказать — там, где расчёт ещё впереди
  const say = (text) => result.replaceChildren(note(text));

  // Позвать к заявке — там, где цены не будет вовсе
  const invite = (text) => {
    const link = document.createElement("a");
    link.className = "link-underline";
    link.href = "#inquiry";
    link.textContent = "Оставить заявку →";
    result.replaceChildren(note(text), link);
  };

  const showTotal = (quote) => {
    const total = document.createElement("div");
    total.className = "calc-total";
    total.textContent = `${window.memiro.rub(quote.total)} ₽`;
    const nodes = [total];
    if (quote.additions.length) {
      const list = document.createElement("ul");
      list.className = "calc-additions";
      quote.additions.forEach((addition) => {
        const item = document.createElement("li");
        const label = document.createElement("span");
        label.textContent = addition.label;
        const amount = document.createElement("b");
        // Отрицательная доплата — скидка: полотно дешевле умолчания
        const sign = addition.amount < 0 ? "−" : "+";
        amount.textContent = `${sign}${window.memiro.rub(Math.abs(addition.amount))} ₽`;
        item.append(label, amount);
        list.append(item);
      });
      nodes.push(list);
    }
    result.replaceChildren(...nodes);
  };

  // Ответы приходят не в порядке отправки: показываем только последний
  // запрошенный, иначе цена мигала бы на предыдущий размер
  let latest = 0;

  const recalculate = async () => {
    // Номер берётся до всякого выхода: стерев ширину, покупатель
    // отменяет и запрос, что уже в полёте, — иначе ответ на прежний
    // размер напечатал бы цену над опустевшим полем
    const ticket = ++latest;
    const sizes = { width_mm: Number(width.value), height_mm: Number(height.value) };
    if (!(sizes.width_mm > 0 && sizes.height_mm > 0)) {
      say(NOTES.sizes);
      return;
    }
    const query = new URLSearchParams({
      product: root.dataset.product,
      width_mm: sizes.width_mm,
      height_mm: sizes.height_mm,
      values: selects.map((select) => select.value).join(","),
    });
    let quote = null;
    try {
      const response = await fetch(`/api/price?${query}`, {
        headers: { Accept: "application/json" },
      });
      if (response.ok) quote = await response.json();
    } catch {
      // Сеть моргнула — заявка остаётся рабочим ответом
    }
    if (ticket !== latest) return;
    if (!quote) {
      invite(NOTES.failed);
      return;
    }
    // Размер за пределом производства цены не получает вовсе
    if (quote.needs_inquiry || quote.total === null) {
      invite(NOTES.inquiry);
      return;
    }
    showTotal(quote);
  };

  // Ввод миллиметров идёт посимвольно: 1900 по пути через 1, 19 и 190
  let typing = null;
  const debounced = () => {
    clearTimeout(typing);
    typing = setTimeout(recalculate, 400);
  };

  [width, height].forEach((field) => {
    field.addEventListener("input", debounced);
    field.addEventListener("change", recalculate);
  });
  selects.forEach((select) =>
    select.addEventListener("change", recalculate),
  );

  recalculate();
})();
