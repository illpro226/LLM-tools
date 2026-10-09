import { cache } from "react";

/** Verse shown on the dashboard, rotated daily. */
export const getVerseOfTheDay = cache(async (): Promise<string> => {
  const day = new Date().getDate();
  return ROTATION[day % ROTATION.length][0];
});

export const LIST_CONFIG: Record<string, { label: string }> = {
  books: { label: "Books" },
  people: { label: "People" },
};

/** Book, chapter, verse. */
const ROTATION: [book: string, chapter: number, verse: number][] = [
  ["John", 3, 16],
  ["Psalms", 23, 1],
];

export const GRANTING_STATUSES: ReadonlySet<string> = new Set([
  "active",
  "trialing",
]);

export function label(slug: string): string {
  const local = LIST_CONFIG[slug];
  return local.label;
}
