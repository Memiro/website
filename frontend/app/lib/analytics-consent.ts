// Роскомнадзор treats the counter's cookies and identifiers as personal data,
// so the answer decides on the server and the counter's number never reaches
// the HTML of a visitor who has not accepted (ADR-0006).
export const CONSENT_COOKIE = "cookie_consent";
export const ACCEPTED = "yes";
export const DECLINED = "no";

// A year — long enough that an accepting visitor reloads the page once a year.
export const CONSENT_MAX_AGE_SECONDS = 31_536_000;

/** What the visitor's answer earns: the counter, the banner asking for one, or neither. */
export type AnalyticsGate = "counter" | "banner" | "silence";

/** Decide what the page carries for a visitor who answered this way. */
export function analyticsGate(counterId: string, answer: string | undefined): AnalyticsGate {
  if (counterId === "") {
    return "silence";
  }
  if (answer === ACCEPTED) {
    return "counter";
  }
  return answer === DECLINED ? "silence" : "banner";
}

/** The counter's number as configured, or an empty string when the contour runs without analytics. */
export function validCounterId(configured: string | undefined): string {
  const trimmed = (configured ?? "").trim();
  return /^\d+$/.test(trimmed) ? trimmed : "";
}
