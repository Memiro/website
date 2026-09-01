import { ApiResponseError, asRecord, requestJson } from "../lib/http.ts";
import type { SubmitInquiryRequest } from "../lib/inquiry-state.ts";

const UNKNOWN_REFUSAL = "INTERNAL_ERROR";
// Sending an inquiry writes: the server stores it and only then notifies the studio, so a
// short abort would hide a stored inquiry behind "try again" and the retry would duplicate it.
const SUBMIT_TIMEOUT_MS = 30_000;

export interface AcceptedInquiry {
  id: string;
}

export class SubmitInquiryError extends Error {
  public readonly code: string;

  public constructor(code: string, cause?: unknown) {
    super(`The inquiry API rejected the request with ${code}`, { cause });
    this.code = code;
  }
}

export async function submitInquiry(
  request: SubmitInquiryRequest,
  apiBaseUrl = window.location.origin,
): Promise<AcceptedInquiry> {
  try {
    return await requestJson({
      url: new URL("/api/inquiries", apiBaseUrl),
      post: request,
      isBody: isAcceptedInquiry,
      timeoutMs: SUBMIT_TIMEOUT_MS,
    });
  } catch (error) {
    throw new SubmitInquiryError(error instanceof ApiResponseError ? error.code ?? UNKNOWN_REFUSAL : UNKNOWN_REFUSAL, error);
  }
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

function isAcceptedInquiry(value: unknown): value is AcceptedInquiry {
  return typeof asRecord(value)?.id === "string";
}
