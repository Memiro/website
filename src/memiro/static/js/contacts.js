// Карта шоурума: iframe вставляется только по клику посетителя —
// виджет Яндекса ставит куки, а согласия до нажатия нет
(() => {
  const box = document.querySelector("[data-map]");
  const button = box && box.querySelector("[data-map-load]");
  if (!button) return;
  button.addEventListener("click", () => {
    const frame = document.createElement("iframe");
    frame.src = box.dataset.mapSrc;
    frame.title = box.dataset.mapTitle;
    frame.allowFullscreen = true;
    box.replaceChildren(frame);
  });
})();
