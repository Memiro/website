import { ApiResponseError } from "./catalog-api";

/** Resolve a catalogue lookup to null when the slug is empty or the API says 404; other failures still throw. */
export async function foundOrNull<Result>(slug: string, load: (slug: string) => Promise<Result>): Promise<Result | null> {
  if (slug === "") {
    return null;
  }
  try {
    return await load(slug);
  } catch (error) {
    if (error instanceof ApiResponseError && error.status === 404) {
      return null;
    }
    throw error;
  }
}
