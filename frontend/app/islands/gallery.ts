/** The product gallery: a thumbnail swaps the main photograph, nothing loads twice. */
export function mountGallery(root: Document): void {
  const main = root.querySelector<HTMLImageElement>("[data-gallery-main]");
  const thumbs = [...root.querySelectorAll<HTMLButtonElement>(".thumbs button")];
  if (main === null || thumbs.length === 0) {
    return;
  }
  for (const thumb of thumbs) {
    thumb.addEventListener("click", () => {
      const source = thumb.dataset.src;
      if (source === undefined) {
        return;
      }
      main.src = source;
      for (const other of thumbs) {
        other.classList.toggle("on", other === thumb);
        other.setAttribute("aria-pressed", String(other === thumb));
      }
    });
  }
}
