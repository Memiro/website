export interface Work {
  image: string;
  title: string;
  // The mirror standing on the photograph, while the catalogue still sells it.
  // A page of installations no one can walk out of is an album; a customer who
  // liked what he sees must be able to reach the thing he is looking at.
  product: WorkProduct | null;
}

export interface WorkProduct {
  categorySlug: string;
  slug: string;
}

// Photographs of installations the studio has done, in the owner's order.
// They are content, not catalogue: the owner replaces them with a commit until
// the admin grows a gallery of its own, and the mirror each one names is a
// hand-written address, not a lookup.
export const WORKS: Work[] = [
  { image: "/img/works/mir-portal-6a15d5da0e366.jpg", product: { categorySlug: "zerkala", slug: "mir-portal" }, title: "Арочное зеркало в спальне" },
  { image: "/img/works/zerkalo-mesyats-halo-moon-6a15d5dec507b.jpg", product: { categorySlug: "zerkala", slug: "zerkalo-mesyats-halo-moon" }, title: "Halo Moon в гостиной" },
  { image: "/img/works/zerkalo-arka-grand-arc-6a15d5f39cc29.jpg", product: { categorySlug: "zerkala", slug: "zerkalo-arka-grand-arc" }, title: "Grand Arc в прихожей" },
  { image: "/img/works/zerkalo-na-dver-full-view-6a15d5dd50f24.jpg", product: { categorySlug: "zerkala", slug: "zerkalo-na-dver-full-view" }, title: "Full View на двери гардеробной" },
  { image: "/img/works/zerkalo-kaplya-dew-glow-6a15d7de287c2.jpg", product: { categorySlug: "zerkala", slug: "zerkalo-kaplya-dew-glow" }, title: "Dew Glow в ванной" },
];
