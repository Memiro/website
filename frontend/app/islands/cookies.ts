import { ACCEPTED, CONSENT_COOKIE, CONSENT_MAX_AGE_SECONDS, DECLINED } from "../lib/analytics-consent.ts";

// A Secure cookie is dropped on plain http, and the dev contour runs there.
function rememberAnswer(answer: string): void {
  const secure = window.location.protocol === "https:" ? "; Secure" : "";
  document.cookie = `${CONSENT_COOKIE}=${answer}; Max-Age=${CONSENT_MAX_AGE_SECONDS}; Path=/; SameSite=Lax${secure}`;
}

/** Wire the banner's two buttons; the counter itself arrives from the server on the next answer. */
export function mountCookieBanner(root: Document): void {
  const banner = root.querySelector<HTMLElement>("[data-cookie-banner]");
  if (banner === null) {
    return;
  }
  banner.querySelector("[data-cookie-accept]")?.addEventListener("click", () => {
    rememberAnswer(ACCEPTED);
    window.location.reload();
  });
  banner.querySelector("[data-cookie-decline]")?.addEventListener("click", () => {
    rememberAnswer(DECLINED);
    banner.remove();
  });
}
