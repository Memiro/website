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
      // The candidates travel with the photograph: a swap that left the old
      // srcset in place would show the browser's pick of the previous photo.
      main.srcset = thumb.dataset.srcset ?? "";
      for (const other of thumbs) {
        other.classList.toggle("on", other === thumb);
        other.setAttribute("aria-pressed", String(other === thumb));
      }
    });
  }
}
