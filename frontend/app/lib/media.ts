// Photographs of products and of installed works alike are stored by key and
// served by the edge under /media/.
const MEDIA_PREFIX = "/media/";
const PLACEHOLDER = "/img/placeholder.svg";

export function mediaUrl(key: string): string {
  return `${MEDIA_PREFIX}${key}`;
}

/** The picture a card shows: the first photograph, or the studio's placeholder. */
export function coverImageUrl(imageKeys: readonly string[]): string {
  const [cover] = imageKeys;
  return cover === undefined ? PLACEHOLDER : mediaUrl(cover);
}

export function hasPhotographs(imageKeys: readonly string[]): boolean {
  return imageKeys.length > 0;
}
