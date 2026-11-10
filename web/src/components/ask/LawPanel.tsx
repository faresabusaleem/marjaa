"use client";

import { ArrowUpRight, X } from "lucide-react";
import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { type Chunk, counterpartId, getChunk } from "@/lib/api";
import { officialUrl } from "@/lib/i18n";
import { type Lang, localePath } from "@/lib/locale";
import { LawText } from "../library/LawText";
import { useLang, useT } from "../site/LangProvider";

/** All parts of an article (long articles are split into -p0, -p1, …). */
async function loadArticle(id: string, partCounts: Record<string, number>): Promise<Chunk[]> {
  const base = id.replace(/-p\d+$/, "");
  if (base === id) return [await getChunk(id)].filter((c): c is Chunk => c !== null);
  const count = partCounts[base] ?? 1;
  const found = await Promise.all(Array.from({ length: count }, (_, p) => getChunk(`${base}-p${p}`)));
  return found.filter((c): c is Chunk => c !== null);
}

/** Drop the "Article (29)" / title lines each part repeats; the panel header shows them. */
function body(parts: Chunk[]): string {
  return parts
    .map((p) => {
      const lines = p.text.split("\n");
      if (/^\s*(Article|المادة)\s*\(\s*\d+\s*\)\s*$/.test(lines[0] ?? "")) lines.shift();
      if (p.title && lines[0]?.trim() === p.title.trim()) lines.shift();
      return lines.join("\n");
    })
    .join("\n");
}

type Versions = Partial<Record<Lang, Chunk[]>> | "error";

interface Props {
  chunkId: string;
  /** Part counts of long articles, by chunk id without the -pN suffix. */
  partCounts: Record<string, number>;
  onClose: () => void;
  /** Bottom sheet on phones and tablets, a column beside the answers on wide screens. */
  wide: boolean;
}

export function LawPanel({ chunkId, partCounts, onClose, wide }: Props) {
  const t = useT();
  const lang = useLang();
  const [versions, setVersions] = useState<Versions | null>(null);
  const [tab, setTab] = useState<Lang>(chunkId.includes("-ar-") ? "ar" : "en");
  const closeRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    let live = true;
    setVersions(null);
    setTab(chunkId.includes("-ar-") ? "ar" : "en");
    Promise.all([loadArticle(chunkId, partCounts), loadArticle(counterpartId(chunkId), partCounts)])
      .then(([own, other]) => {
        if (!live) return;
        const v: Partial<Record<Lang, Chunk[]>> = {};
        for (const parts of [own, other]) if (parts.length) v[parts[0].language] = parts;
        setVersions(Object.keys(v).length ? v : "error");
      })
      .catch(() => live && setVersions("error"));
    return () => {
      live = false;
    };
  }, [chunkId, partCounts]);

  useEffect(() => {
    closeRef.current?.focus({ preventScroll: wide });
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [chunkId, onClose, wide]);

  const loaded = versions && versions !== "error" ? versions : null;
  const parts = loaded?.[tab];
  const head = parts?.[0] ?? loaded?.ar?.[0] ?? loaded?.en?.[0];
  const article = head?.article ?? Number(chunkId.match(/-a(\d{3})/)?.[1] ?? 0);
  const titleFor = (l: Lang) => loaded?.[l]?.find((c) => c.title)?.title ?? "";
  const pages = parts?.length ? t.panel.pages(parts[0].page_start, parts.at(-1)!.page_end) : "";

  const panel = (
    <aside
      role={wide ? "complementary" : "dialog"}
      aria-modal={wide ? undefined : true}
      aria-labelledby="panel-title"
      className={
        wide
          ? "panel-in sticky top-6 flex max-h-[calc(100dvh-8rem)] flex-col rounded-lg bg-surface"
          : "sheet-in fixed inset-x-0 bottom-0 z-50 flex max-h-[88dvh] flex-col rounded-t-lg bg-surface shadow-float"
      }
    >
      {!wide && <span className="mx-auto mt-2.5 h-1 w-10 rounded-full bg-line-strong" aria-hidden />}
      <div className="flex items-start gap-3 px-5 pb-4 pt-4 sm:px-6">
        <div className="min-w-0 flex-1">
          <p className="text-caption text-ink-muted">{lang === "ar" ? head?.law_name_ar ?? " " : head?.law_name_en ?? " "}</p>
          <h2 id="panel-title" className="mt-1 text-h3 font-semibold">
            {t.panel.article(article)}
            {titleFor(lang) && <span className="font-normal text-ink-muted">: {titleFor(lang)}</span>}
          </h2>
        </div>
        <button
          ref={closeRef}
          type="button"
          onClick={onClose}
          aria-label={t.panel.close}
          title={t.panel.close}
          className="-me-2 grid size-10 shrink-0 place-items-center rounded-md text-ink-muted transition-colors hover:bg-surface-strong hover:text-ink"
        >
          <X size={20} strokeWidth={1.75} aria-hidden />
        </button>
      </div>

      <div role="tablist" aria-label={t.panel.article(article)} className="mx-5 grid grid-cols-2 rounded-md bg-bg p-1 sm:mx-6">
        {(["ar", "en"] as const).map((l) => (
          <button
            key={l}
            type="button"
            role="tab"
            aria-selected={tab === l}
            disabled={loaded !== null && !loaded[l]}
            onClick={() => setTab(l)}
            className={`rounded-sm px-3 py-1.5 text-start transition-colors disabled:opacity-40 ${
              tab === l ? "bg-surface-strong text-ink" : "text-ink-muted hover:text-ink"
            }`}
          >
            <span className="block text-small font-medium">{l === "ar" ? t.panel.arabic : t.panel.english}</span>
            <span className="block text-caption text-ink-muted">{l === "ar" ? t.panel.authoritative : t.panel.translation}</span>
          </button>
        ))}
      </div>

      <div role="tabpanel" className="min-h-0 flex-1 overflow-y-auto px-5 py-5 sm:px-6">
        {versions === null ? (
          <div className="space-y-3" aria-hidden>
            {[94, 100, 86, 97, 62].map((w, i) => (
              <div key={i} className="skeleton h-4" style={{ width: `${w}%` }} />
            ))}
          </div>
        ) : versions === "error" ? (
          <p className="text-small text-ink-muted">{t.panel.loadError}</p>
        ) : parts ? (
          <LawText text={body(parts)} lang={tab} />
        ) : (
          <p className="text-small text-ink-muted">{t.panel.missing}</p>
        )}
      </div>

      <div className="flex flex-wrap items-center gap-x-5 gap-y-2 border-t border-line px-5 py-3.5 text-caption sm:px-6">
        <span className="text-ink-muted">{pages}</span>
        <span className="ms-auto flex gap-4">
          {article > 0 && (
            <Link href={localePath(lang, `/library/${article}`)} className="link">
              {t.panel.openLibrary}
            </Link>
          )}
          <a href={officialUrl(lang)} target="_blank" rel="noreferrer" className="link inline-flex items-center gap-0.5">
            {t.panel.official}
            <ArrowUpRight size={13} strokeWidth={1.75} className="rtl:-scale-x-100" aria-hidden />
          </a>
        </span>
      </div>
    </aside>
  );

  if (wide) return panel;
  return (
    <>
      <button type="button" aria-label={t.panel.close} tabIndex={-1} onClick={onClose} className="fixed inset-0 z-40 bg-scrim" />
      {panel}
    </>
  );
}
