// Vite replaces `import.meta.env.X` while building, so a value read that way is
// frozen into the image: the API address in docker-compose would be decoration
// and would silently keep working only while it equalled the default. The
// address has to come from the process the container runs.
const DEFAULT_INTERNAL_API_BASE_URL = "http://api:8000";

/** The contour's internal address for the API, as the server-rendered pages reach it. */
export function internalApiBaseUrl(): string {
  const configured = (process.env.API_INTERNAL_URL ?? "").trim();
  return configured === "" ? DEFAULT_INTERNAL_API_BASE_URL : configured;
}
