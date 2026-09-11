import type { ProductImage } from "./catalog-api.ts";

// Photographs of products and of installed works alike are stored by key and
// served by the edge under /media/.
const MEDIA_PREFIX = "/media/";
const PLACEHOLDER = "/img/placeholder.svg";

export function mediaUrl(key: string): string {
  return `${MEDIA_PREFIX}${key}`;
}

/** The candidates the browser picks from: every copy the storage holds, by its width. */
export function imageSrcSet(image: ProductImage | undefined | null): string | undefined {
  if (image === undefined || image === null || image.variants.length === 0) {
    return undefined;
  }
  return image.variants.map((variant) => `${mediaUrl(variant.key)} ${variant.width}w`).join(", ");
}

/** The address of one photograph, or the studio's placeholder where there is none. */
export function photographUrl(image: ProductImage | undefined | null): string {
  return image === undefined || image === null ? PLACEHOLDER : mediaUrl(image.key);
}
