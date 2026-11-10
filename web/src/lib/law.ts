// The Labour Law text for the Library (server side). src/data/law.json is
// written by scripts/export_law.py from the hosted chunks.

import law from "@/data/law.json";
import type { Lang } from "./locale";
import type { RawEntry } from "./search";

export interface Version {
  title: string;
  text: string;
  pages: number[];
  chunks: string[];
}

export interface Article {
  n: number;
  ar: Version;
  en: Version;
}

export const LAW = law.law;
export const ARTICLES = law.articles as Article[];
export const PREAMBLE = law.preamble as { ar: Version; en: Version };

export const getArticle = (n: number): Article | undefined => ARTICLES.find((a) => a.n === n);

/** The article a chunk id belongs to: "labour_law_2021-en-a029-p1" -> 29. */
export function articleOfChunk(id: string): number | null {
  const m = id.match(/-a(\d{3})(?:-p\d+)?$/);
  return m ? Number(m[1]) : null;
}

export const titleOf = (a: Article, lang: Lang) => a[lang].title || a[lang === "ar" ? "en" : "ar"].title;

/** The search index the Library downloads on first use (served at /law-index.json). */
export function searchIndex(): RawEntry[] {
  const flat = (s: string) => s.replace(/\s+/g, " ").trim();
  return ARTICLES.map((a) => ({
    n: a.n,
    titles: { ar: a.ar.title, en: a.en.title },
    text: { ar: flat(a.ar.text), en: flat(a.en.text) },
  }));
}
