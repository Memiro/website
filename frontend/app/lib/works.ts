export interface Work {
  image: string;
  title: string;
}

// Photographs of installations the studio has done, in the owner's order.
// They are content, not catalogue: no product hangs on them, and the owner
// replaces them with a commit until the admin grows a gallery of its own.
export const WORKS: Work[] = [
  { image: "/img/works/mir-portal-6a15d5da0e366.jpg", title: "Арочное зеркало в спальне" },
  { image: "/img/works/zerkalo-mesyats-halo-moon-6a15d5dec507b.jpg", title: "Halo Moon в гостиной" },
  { image: "/img/works/zerkalo-arka-grand-arc-6a15d5f39cc29.jpg", title: "Grand Arc в прихожей" },
  { image: "/img/works/zerkalo-na-dver-full-view-6a15d5dd50f24.jpg", title: "Full View на двери гардеробной" },
  { image: "/img/works/zerkalo-kaplya-dew-glow-6a15d7de287c2.jpg", title: "Dew Glow в ванной" },
];
