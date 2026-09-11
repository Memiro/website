import type { TileSpan } from "./tiles.ts";

/**
 * How wide a picture will really be drawn, in the terms the browser needs
 * before it has any layout: the media queries here are the ones the stylesheet
 * changes the columns at (`global.css`). One `100vw` for everything would undo
 * the srcset — it would hand a phone the widest copy there is.
 */

// .grid-4: four columns, three below 1180px, two below 900px, one below 480px.
export const CARD_SIZES = "(max-width: 480px) 100vw, (max-width: 900px) 50vw, (max-width: 1180px) 33vw, 25vw";

// .bento: four columns, two below 900px. A tile spanning two of four columns
// is half the page; a single cell is a quarter of it.
const HALF_OF_THE_PAGE = "(max-width: 900px) 100vw, 50vw";
const QUARTER_OF_THE_PAGE = "(max-width: 900px) 50vw, 25vw";

// .pdp: the gallery takes a little over half the page and stands alone below
// 1180px, where it is the width of the page.
export const GALLERY_SIZES = "(max-width: 1180px) 100vw, 55vw";

/** The width of one bento tile, which follows the span it was given. */
export function tileSizes(span: TileSpan): string {
  return span === "1x1" ? QUARTER_OF_THE_PAGE : HALF_OF_THE_PAGE;
}
