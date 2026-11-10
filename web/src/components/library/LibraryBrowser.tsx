"use client";

import { ArrowRight, Search, X } from "lucide-react";
import Link from "next/link";
import { useEffect, useMemo, useRef, useState } from "react";
import { type Lang, localePath } from "@/lib/locale";
import { buildIndex, excerpt, type IndexEntry, type RawEntry, search } from "@/lib/search";
import { useLang, useT } from "../site/LangProvider";

export interface Row {
  n: number;
  ar: string;
  en: string;
}

let indexPromise: Promise<{ raw: Map<number, RawEntry>; index: IndexEntry[] }> | null = null;
function loadIndex() {
  indexPromise ??= fetch("/law-index.json")
    .then((r) => r.json() as Promise<RawEntry[]>)
    .then((raw) => ({ raw: new Map(raw.map((r) => [r.n, r])), index: buildIndex(raw) }));
  return indexPromise;
}

/** The article index with full-text search in both languages. */
export function LibraryBrowser({ rows }: { rows: Row[] }) {
  const t = useT();
  const lang = useLang();
  const other: Lang = lang === "ar" ? "en" : "ar";
  const [query, setQuery] = useState("");
  const [data, setData] = useState<Awaited<ReturnType<typeof loadIndex>> | null>(null);
  const [failed, setFailed] = useState(false);
  const input = useRef<HTMLInputElement>(null);

  const warm = () => {
    if (data || failed) return;
    loadIndex().then(setData, () => setFailed(true));
  };
  useEffect(() => {
    if (query) warm();
  });

  const hits = useMemo(() => (data && query.trim() ? search(data.index, query) : null), [data, query]);
  const byN = useMemo(() => new Map(rows.map((r) => [r.n, r])), [rows]);
  const searching = query.trim().length > 0;

  return (
    <div>
      <div className="relative max-w-2xl">
        <label htmlFor="library-search" className="mb-2 block text-small font-medium text-ink">
          {t.library.searchLabel}
        </label>
        <div className="relative">
          <Search size={18} strokeWidth={1.75} className="pointer-events-none absolute start-4 top-1/2 -translate-y-1/2 text-ink-muted" aria-hidden />
          <input
            id="library-search"
            ref={input}
            type="search"
            value={query}
            onFocus={warm}
            onChange={(e) => setQuery(e.target.value)}
            placeholder={t.library.searchPlaceholder}
            autoComplete="off"
            dir={query ? "auto" : undefined}
            className="h-13 w-full rounded-lg border border-line-strong bg-surface pe-12 ps-12 text-body text-ink outline-none transition-colors focus:border-brand-sea focus:outline focus:outline-1 focus:outline-brand-sea [&::-webkit-search-cancel-button]:hidden"
          />
          {query && (
            <button
              type="button"
              onClick={() => {
                setQuery("");
                input.current?.focus();
              }}
              aria-label={t.library.clear}
              className="absolute end-2 top-1/2 grid size-9 -translate-y-1/2 place-items-center rounded-md text-ink-muted hover:bg-surface-strong hover:text-ink"
            >
              <X size={18} strokeWidth={1.75} aria-hidden />
            </button>
          )}
        </div>
        <p className="mt-2 min-h-6 text-small text-ink-muted" aria-live="polite">
          {searching && (hits ? (hits.length ? t.library.matches(hits.length) : t.library.noMatches) : failed ? "" : t.library.loading)}
        </p>
      </div>

      {searching && hits ? (
        <ol className="mt-6 border-t border-line">
          {hits.map((h) => {
            const row = byN.get(h.n)!;
            const raw = data!.raw.get(h.n)!;
            const ex = excerpt(raw.text[lang], query) ?? excerpt(raw.text[other], query);
            const exLang = excerpt(raw.text[lang], query) ? lang : other;
            return (
              <li key={h.n}>
                <Link
                  href={localePath(lang, `/library/${h.n}`)}
                  className="group grid grid-cols-[3.5rem_minmax(0,1fr)] gap-x-4 border-b border-line py-4 transition-colors hover:bg-surface sm:grid-cols-[5rem_minmax(0,1fr)]"
                >
                  <span className="tabular ps-1 text-h3 font-semibold text-ink-muted group-hover:text-accent">{h.n}</span>
                  <span className="min-w-0">
                    <span className="block font-medium text-ink group-hover:text-accent">{row[lang] || row[other] || t.library.untitled}</span>
                    {ex && (
                      <span className="mt-1 block text-small text-ink-muted" lang={exLang} dir={exLang === "ar" ? "rtl" : "ltr"}>
                        {ex.before} <mark className="rounded-sm bg-accent-subtle px-0.5 text-ink">{ex.match}</mark> {ex.after}
                      </span>
                    )}
                  </span>
                </Link>
              </li>
            );
          })}
        </ol>
      ) : (
        <ArticleIndex rows={rows} />
      )}
    </div>
  );
}

function ArticleIndex({ rows }: { rows: Row[] }) {
  const t = useT();
  const lang = useLang();
  const other: Lang = lang === "ar" ? "en" : "ar";
  return (
    <div className="mt-6">
      <div className="hidden grid-cols-[5rem_minmax(0,1fr)_minmax(0,1fr)_1.5rem] gap-x-6 border-b border-line-strong pb-2 text-small text-ink-muted md:grid">
        <span className="ps-1">{t.library.colArticle}</span>
        <span>{t.library.colTitle}</span>
        <span lang={other} dir={other === "ar" ? "rtl" : "ltr"}>
          {other === "ar" ? "العنوان" : "Title"}
        </span>
        <span />
      </div>
      <ol>
        <li>
          <Link
            href={localePath(lang, "/library/preamble")}
            className="group grid grid-cols-[3.5rem_minmax(0,1fr)] items-baseline gap-x-4 border-b border-line py-4 transition-colors hover:bg-surface md:grid-cols-[5rem_minmax(0,1fr)_minmax(0,1fr)_1.5rem] md:gap-x-6"
          >
            <span className="ps-1 text-ink-muted" aria-hidden>
              §
            </span>
            <span className="font-medium text-ink group-hover:text-accent">
              {t.library.preamble}
              <span className="mt-0.5 block text-small font-normal text-ink-muted">{t.library.preambleNote}</span>
            </span>
            <span className="hidden text-ink-muted md:block" lang={other} dir={other === "ar" ? "rtl" : "ltr"}>
              {other === "ar" ? "الديباجة" : "Preamble"}
            </span>
            <Arrow />
          </Link>
        </li>
        {rows.map((r) => (
          <li key={r.n}>
            <Link
              href={localePath(lang, `/library/${r.n}`)}
              className="group grid grid-cols-[3.5rem_minmax(0,1fr)] items-baseline gap-x-4 border-b border-line py-3.5 transition-colors hover:bg-surface md:grid-cols-[5rem_minmax(0,1fr)_minmax(0,1fr)_1.5rem] md:gap-x-6"
            >
              <span className="tabular ps-1 font-medium text-ink-muted group-hover:text-accent">{r.n}</span>
              <span className="font-medium text-ink group-hover:text-accent">
                {r[lang] || <span className="font-normal text-ink-muted">{t.library.untitled}</span>}
                {r[other] && (
                  <span className="mt-0.5 block text-small font-normal text-ink-muted md:hidden" lang={other} dir={other === "ar" ? "rtl" : "ltr"}>
                    {r[other]}
                  </span>
                )}
              </span>
              <span className="hidden text-ink-muted md:block" lang={other} dir={other === "ar" ? "rtl" : "ltr"}>
                {r[other]}
              </span>
              <Arrow />
            </Link>
          </li>
        ))}
      </ol>
    </div>
  );
}

function Arrow() {
  return (
    <ArrowRight
      size={18}
      strokeWidth={1.75}
      className="hidden self-center text-ink-muted opacity-0 transition-opacity group-hover:opacity-100 md:block rtl:-scale-x-100"
      aria-hidden
    />
  );
}
