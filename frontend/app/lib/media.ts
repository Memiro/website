// Product photographs are stored by key and served by the edge under /media/.
const MEDIA_PREFIX = "/media/";
const PLACEHOLDER = "/img/placeholder.svg";

export function productImageUrl(key: string): string {
  return `${MEDIA_PREFIX}${key}`;
}

/** The picture a card shows: the first photograph, or the studio's placeholder. */
export function coverImageUrl(imageKeys: readonly string[]): string {
  const [cover] = imageKeys;
  return cover === undefined ? PLACEHOLDER : productImageUrl(cover);
}

export function hasPhotographs(imageKeys: readonly string[]): boolean {
  return imageKeys.length > 0;
}
