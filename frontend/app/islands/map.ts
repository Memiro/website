/** The showroom map arrives on a click: the Yandex widget sets cookies of its own. */
export function mountShowroomMap(root: Document): void {
  const box = root.querySelector<HTMLElement>("[data-map]");
  const button = box?.querySelector<HTMLElement>("[data-map-load]");
  if (box === null || button === undefined || button === null) {
    return;
  }
  button.addEventListener("click", () => {
    const frame = document.createElement("iframe");
    frame.src = box.dataset.mapSrc ?? "";
    frame.title = box.dataset.mapTitle ?? "";
    frame.allowFullscreen = true;
    box.replaceChildren(frame);
  });
}
