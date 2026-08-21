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
