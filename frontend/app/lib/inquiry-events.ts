/** The header counter and the inquiry page live outside the island that edits the basket. */
export const INQUIRY_CHANGED_EVENT = "memiro:inquiry-changed";

export function notifyInquiryChanged(target: EventTarget): void {
  target.dispatchEvent(new CustomEvent(INQUIRY_CHANGED_EVENT));
}
