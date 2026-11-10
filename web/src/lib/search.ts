// Library search: every query word must appear in an article (title or text, in
// either language). Arabic is normalised the way the backend's BM25 does it:
// no diacritics or tatweel, one form of alef, ya and ta marbuta, Western digits.

/** What /law-index.json holds for each article. */
export interface RawEntry {
  n: number;
  titles: { ar: string; en: string };
  text: { ar: string; en: string };
}

export interface IndexEntry {
  n: number;
  titles: { ar: string; en: string };
  /** Normalised words of the whole article, both languages. */
  words: string;
  /** Normalised title words, both languages. */
  titleWords: string;
}

export function buildIndex(raw: RawEntry[]): IndexEntry[] {
  return raw.map((r) => ({
    n: r.n,
    titles: r.titles,
    titleWords: normalize(`${r.titles.ar} ${r.titles.en}`),
    words: normalize(`${r.titles.ar} ${r.titles.en} ${r.text.ar} ${r.text.en}`),
  }));
}

export interface Hit {
  n: number;
  score: number;
}

const DIACRITICS = /[\u064B-\u065F\u0670\u0640]/g;

export function normalize(text: string): string {
  return text
    .normalize("NFKC")
    .toLowerCase()
    .replace(DIACRITICS, "")
    .replace(/[أإآٱ]/g, "ا")
    .replace(/ى/g, "ي")
    .replace(/ة/g, "ه")
    .replace(/ؤ/g, "و")
    .replace(/ئ/g, "ي")
    .replace(/[٠-٩]/g, (d) => String(d.charCodeAt(0) - 0x0660))
    .replace(/[^\p{L}\p{N}]+/gu, " ")
    .trim();
}

/** Query words; the Arabic article "ال" is dropped so "الإجازة" also finds "إجازة". */
export function terms(query: string): string[] {
  return normalize(query)
    .split(" ")
    .filter(Boolean)
    .map((w) => (w.length > 4 && w.startsWith("ال") ? w.slice(2) : w));
}

export function search(index: IndexEntry[], query: string): Hit[] {
  const words = terms(query);
  if (!words.length) return [];
  const number = /^\d{1,3}$/.test(words[0]) && words.length === 1 ? Number(words[0]) : null;
  const hits: Hit[] = [];
  for (const entry of index) {
    if (number !== null && entry.n === number) {
      hits.push({ n: entry.n, score: 100 });
      continue;
    }
    let score = 0;
    let all = true;
    for (const w of words) {
      const inTitle = entry.titleWords.includes(w);
      const inText = entry.words.includes(w);
      if (!inTitle && !inText) {
        all = false;
        break;
      }
      score += inTitle ? 3 : 1;
    }
    if (all) hits.push({ n: entry.n, score });
  }
  return hits.sort((a, b) => b.score - a.score || a.n - b.n);
}

/** A short excerpt of `text` around the first query word, with the match marked. */
export function excerpt(text: string, query: string, radius = 70): { before: string; match: string; after: string } | null {
  const words = terms(query);
  if (!words.length) return null;
  const tokens = text.replace(/\s+/g, " ").split(" ");
  const at = tokens.findIndex((t) => words.some((w) => normalize(t).includes(w)));
  if (at === -1) return null;
  const before = tokens.slice(0, at).join(" ");
  const after = tokens.slice(at + 1).join(" ");
  const cut = (s: string, fromEnd: boolean) =>
    s.length <= radius ? s : fromEnd ? `…${s.slice(s.length - radius).replace(/^\S*\s/, "")}` : `${s.slice(0, radius).replace(/\s\S*$/, "")}…`;
  return { before: cut(before, true), match: tokens[at], after: cut(after, false) };
}
