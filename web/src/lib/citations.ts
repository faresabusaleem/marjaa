// Splits an answer into text and citation pieces. The pattern mirrors
// CITATION_RE in src/marjaa/generation/citations.py, so a chip appears exactly
// where the backend looked for (and verified) a citation.

import type { Citation, Lang, Source } from "./api";

const CITATION_RE =
  /\[\s*([^[\]]{2,150}?)\s*[,،]\s*(?:Articles?|Art\.?|المادتين|المادتان|المواد|المادة|مادة)\s*([^[\]]{1,40}?)\s*\]/g;
const NUMBER_RE = /[0-9٠-٩]{1,3}/g;

export type Piece = { kind: "text"; text: string } | { kind: "cite"; raw: string; articles: number[] };

export function toAsciiDigits(s: string): string {
  return s.replace(/[٠-٩]/g, (d) => String(d.charCodeAt(0) - 0x0660));
}

export function splitCitations(text: string): Piece[] {
  const pieces: Piece[] = [];
  let last = 0;
  for (const m of text.matchAll(CITATION_RE)) {
    const start = m.index ?? 0;
    if (start > last) pieces.push({ kind: "text", text: text.slice(last, start) });
    const articles = [...m[2].matchAll(NUMBER_RE)].map((n) => Number(toAsciiDigits(n[0])));
    pieces.push({ kind: "cite", raw: m[0], articles });
    last = start + m[0].length;
  }
  if (last < text.length) pieces.push({ kind: "text", text: text.slice(last) });
  return pieces;
}

export type CiteState = "pending" | "verified" | "unverified";

export interface ResolvedCite {
  article: number;
  state: CiteState;
  chunkId: string | null;
}

/** Match a cited article to its verification result and to a retrieved chunk. */
export function resolveCite(
  article: number,
  raw: string,
  sources: Source[],
  citations: Citation[] | null,
  lang: Lang,
): ResolvedCite {
  const candidates = sources.filter((s) => s.article === article);
  const source = candidates.find((s) => s.language === lang) ?? candidates[0];
  if (!citations) return { article, state: "pending", chunkId: source?.id ?? null };
  const check =
    citations.find((c) => c.article === article && c.text === raw) ??
    citations.find((c) => c.article === article);
  const valid = Boolean(check?.valid);
  return {
    article,
    state: valid ? "verified" : "unverified",
    chunkId: check?.chunk_id ?? source?.id ?? null,
  };
}

/** Minimal inline formatting for model output: **bold** only. */
export function splitBold(text: string): { bold: boolean; text: string }[] {
  return text
    .split(/(\*\*[^*]+\*\*)/g)
    .filter(Boolean)
    .map((t) => (t.startsWith("**") && t.endsWith("**") ? { bold: true, text: t.slice(2, -2) } : { bold: false, text: t }));
}
