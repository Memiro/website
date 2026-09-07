const CHOICE_STORAGE_KEY = "memiro.analytics-consent";
const ACCEPTED = "accepted";
const DECLINED = "declined";

function readChoice(): string | null {
  try {
    return window.localStorage.getItem(CHOICE_STORAGE_KEY);
  } catch {
    return null;
  }
}

function rememberChoice(choice: string): void {
  try {
    window.localStorage.setItem(CHOICE_STORAGE_KEY, choice);
  } catch {
    return;
  }
}

function loadMetrika(counterId: string): void {
  const script = document.createElement("script");
  script.async = true;
  script.src = "https://mc.yandex.ru/metrika/tag.js";
  script.addEventListener("load", () => {
    const metrika = (window as unknown as Record<string, unknown>).ym;
    if (typeof metrika === "function") {
      (metrika as (id: string, action: string, options: Record<string, boolean>) => void)(counterId, "init", {
        clickmap: true,
        trackLinks: true,
        accurateTrackBounce: true,
      });
    }
  });
  document.head.append(script);
}

export function mountCookieBanner(root: Document): void {
  const banner = root.querySelector<HTMLElement>("[data-cookie-banner]");
  const counterId = banner?.dataset.metrikaId ?? "";
  if (banner === null || counterId === "") {
    return;
  }
  const choice = readChoice();
  if (choice === ACCEPTED) {
    loadMetrika(counterId);
    return;
  }
  if (choice === DECLINED) {
    return;
  }
  banner.hidden = false;
  banner.querySelector("[data-cookie-accept]")?.addEventListener("click", () => {
    rememberChoice(ACCEPTED);
    banner.hidden = true;
    loadMetrika(counterId);
  });
  banner.querySelector("[data-cookie-decline]")?.addEventListener("click", () => {
    rememberChoice(DECLINED);
    banner.hidden = true;
  });
}
