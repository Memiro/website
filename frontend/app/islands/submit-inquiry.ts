import type { SubmitInquiryRequest } from "../lib/inquiry-state";

export class SubmitInquiryError extends Error {
  public readonly code: string;

  public constructor(code: string) {
    super(`The inquiry API rejected the request with ${code}`);
    this.code = code;
  }
}

export async function submitInquiry(
  request: SubmitInquiryRequest,
  apiBaseUrl = window.location.origin,
): Promise<{ id: string }> {
  const response = await fetch(new URL("/api/inquiries", apiBaseUrl), {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(request),
  });
  if (!response.ok) {
    const body = (await response.json()) as { code?: string };
    throw new SubmitInquiryError(body.code ?? "INTERNAL_ERROR");
  }
  return (await response.json()) as { id: string };
}

export function inquiryErrorMessage(error: SubmitInquiryError): string {
  const messages: Record<string, string> = {
    CONSENT_REQUIRED: "Подтвердите согласие на обработку персональных данных.",
    EMPTY_INQUIRY: "Добавьте хотя бы одну конфигурацию в заявку.",
    INQUIRY_SOURCE_NOT_ACCEPTED: "Эту форму заявки больше нельзя отправить. Обновите страницу и попробуйте снова.",
    INVALID_INQUIRY_CONTENTS: "Состав заявки изменился. Обновите страницу и попробуйте снова.",
    PRODUCT_NOT_FOUND: "Один из выбранных товаров больше недоступен. Обновите страницу и попробуйте снова.",
    ATTRIBUTE_VALUE_NOT_FOUND: "Одна из выбранных опций больше недоступна. Обновите страницу и попробуйте снова.",
    VALIDATION_ERROR: "Проверьте заполнение формы и попробуйте снова.",
  };
  return messages[error.code] ?? "Не удалось отправить заявку. Попробуйте ещё раз.";
}
