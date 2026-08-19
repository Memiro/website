// Галерея карточки товара: переключение главного кадра по миниатюрам
(() => {
  const main = document.querySelector("[data-gallery-main]");
  const thumbs = document.querySelectorAll(".thumbs button");
  if (!main || !thumbs.length) return;
  thumbs.forEach((thumb) => {
    thumb.addEventListener("click", () => {
      thumbs.forEach((other) => other.classList.remove("on"));
      thumb.classList.add("on");
      main.src = thumb.dataset.src;
    });
  });
})();
