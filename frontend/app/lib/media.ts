import type { ProductImage } from "./catalog-api.ts";

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

/** The candidates the browser picks from: every copy the storage holds, by its width. */
export function imageSrcSet(image: ProductImage | undefined): string | undefined {
  if (image === undefined || image.variants.length === 0) {
    return undefined;
  }
  return image.variants.map((variant) => `${mediaUrl(variant.key)} ${variant.width}w`).join(", ");
}

/** The photograph a card stands on: the first of the gallery, copies and all. */
export function coverImage(images: readonly ProductImage[]): ProductImage | undefined {
  const [cover] = images;
  return cover;
}
