export const API_TIMEOUT_MS = 5000;

export class ApiResponseError extends Error {
  public readonly status: number;
  public readonly code: string | null;

  public constructor(status: number, code: string | null) {
    super(`The API answered HTTP ${status}${code === null ? "" : ` (${code})`}`);
    this.status = status;
    this.code = code;
  }
}

export class ApiPayloadError extends Error {
  public constructor(url: URL) {
    super(`The API answer from ${url.pathname} does not match the contract`);
  }
}

export class ApiUnreachableError extends Error {
  public constructor(url: URL, cause: unknown) {
    super(`The API at ${url.origin} did not answer`, { cause });
  }
}

export interface JsonRequest<Body> {
  url: URL;
  isBody: (value: unknown) => value is Body;
  post?: unknown;
  timeoutMs?: number;
}

/** Ask the API for JSON, refusing anything that is late, broken or off-contract. */
export async function requestJson<Body>({ url, isBody, post, timeoutMs = API_TIMEOUT_MS }: JsonRequest<Body>): Promise<Body> {
  let response: Response;
  try {
    response = await fetch(url, {
      method: post === undefined ? "GET" : "POST",
      headers: post === undefined ? undefined : { "content-type": "application/json" },
      body: post === undefined ? undefined : JSON.stringify(post),
      signal: AbortSignal.timeout(timeoutMs),
    });
  } catch (cause) {
    throw new ApiUnreachableError(url, cause);
  }
  // The status is the answer even when the body is: a truncated 404 is still a 404.
  const payload = await jsonPayload(response);
  if (!response.ok) {
    throw new ApiResponseError(response.status, errorCode(payload));
  }
  if (!isBody(payload)) {
    throw new ApiPayloadError(url);
  }
  return payload;
}

export function asRecord(value: unknown): Record<string, unknown> | null {
  return typeof value === "object" && value !== null && !Array.isArray(value) ? (value as Record<string, unknown>) : null;
}

// A proxy in front of the API answers HTML, so the body is parsed only when the API claims JSON.
async function jsonPayload(response: Response): Promise<unknown> {
  if (!(response.headers.get("content-type") ?? "").includes("application/json")) {
    return null;
  }
  try {
    return (await response.json()) as unknown;
  } catch {
    return null;
  }
}

function errorCode(payload: unknown): string | null {
  const code = asRecord(payload)?.code;
  return typeof code === "string" ? code : null;
}
