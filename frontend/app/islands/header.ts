import { INQUIRY_CHANGED_EVENT } from "../lib/inquiry-events.ts";
import { loadInquiryItems } from "../lib/inquiry-state.ts";

function toggleMenu(button: HTMLElement, menu: HTMLElement): void {
  const willOpen = button.getAttribute("aria-expanded") !== "true";
  button.setAttribute("aria-expanded", String(willOpen));
  menu.hidden = !willOpen;
}

function refreshCounter(counter: HTMLElement): void {
  const count = loadInquiryItems(window.localStorage).length;
  counter.textContent = String(count);
  counter.hidden = count === 0;
}

export function mountHeader(root: Document): void {
  const button = root.querySelector<HTMLElement>("[data-menu-toggle]");
  const menu = root.querySelector<HTMLElement>("#mobile-menu");
  if (button !== null && menu !== null) {
    button.addEventListener("click", () => toggleMenu(button, menu));
  }
  const counter = root.querySelector<HTMLElement>("[data-inquiry-counter]");
  if (counter === null) {
    return;
  }
  refreshCounter(counter);
  window.addEventListener(INQUIRY_CHANGED_EVENT, () => refreshCounter(counter));
  window.addEventListener("storage", () => refreshCounter(counter));
}
