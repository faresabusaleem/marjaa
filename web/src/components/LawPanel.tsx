"use client";

import { useEffect, useState } from "react";
import { type Chunk, counterpartId, getChunk, type Lang } from "@/lib/api";
import { OFFICIAL_URL } from "@/lib/i18n";
import { External, X } from "./Icons";
import { usePrefs } from "./Prefs";

/** All parts of an article (long articles are split into -p0, -p1, …). */
async function loadArticle(id: string): Promise<Chunk[]> {
  const base = id.replace(/-p\d+$/, "");
  if (base === id) return [await getChunk(id)].filter((c): c is Chunk => c !== null);
  const parts = await Promise.all([0, 1, 2, 3, 4, 5].map((p) => getChunk(`${base}-p${p}`)));
  return parts.filter((c): c is Chunk => c !== null);
}

type Versions = Partial<Record<Lang, Chunk[]>>;

export function LawPanel({ chunkId, onClose }: { chunkId: string; onClose: () => void }) {
  const { t } = usePrefs();
  const [versions, setVersions] = useState<Versions | null>(null);
  const [tab, setTab] = useState<Lang>(chunkId.includes("-ar-") ? "ar" : "en");

  useEffect(() => {
    let live = true;
    setVersions(null);
    setTab(chunkId.includes("-ar-") ? "ar" : "en");
    Promise.all([loadArticle(chunkId), loadArticle(counterpartId(chunkId))]).then(([own, other]) => {
      if (!live) return;
      const v: Versions = {};
      for (const parts of [own, other]) if (parts.length) v[parts[0].language] = parts;
      setVersions(v);
    });
    return () => {
      live = false;
    };
  }, [chunkId]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  const parts = versions?.[tab];
  const head = parts?.[0];
  const pages = parts?.length ? t.pages(parts[0].page_start, parts.at(-1)!.page_end) : "";

  return (
    <>
      {/* Mobile: dimmed backdrop behind a bottom sheet. */}
      <button
        type="button"
        aria-label={t.close}
        onClick={onClose}
        className="fixed inset-0 z-40 bg-black/30 lg:hidden"
      />
      <aside
        aria-label={head ? `${t.article} ${head.article}` : t.article}
        className="rise fixed inset-x-0 bottom-0 z-50 flex max-h-[85dvh] flex-col rounded-t-2xl border border-line bg-surface shadow-card lg:sticky lg:top-[4.5rem] lg:z-0 lg:max-h-[calc(100dvh-6rem)] lg:rounded-2xl"
      >
        <div className="flex items-start gap-3 border-b border-line px-5 pb-3 pt-4">
          <div className="min-w-0 flex-1" dir={tab === "ar" ? "rtl" : "ltr"}>
            <p className="truncate text-xs text-muted">
              {head ? (tab === "ar" ? head.law_name_ar : head.law_name_en) : " "}
            </p>
            <h2 className="mt-0.5 text-lg font-semibold leading-snug">
              {head ? (
                <>
                  {tab === "ar" ? `المادة ${head.article}` : `Article ${head.article}`}
                  {head.title && <span className="font-normal text-muted"> · {head.title}</span>}
                </>
              ) : (
                <span className="skeleton inline-block h-5 w-40 align-middle" />
              )}
            </h2>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="grid size-8 shrink-0 place-items-center rounded-md text-muted hover:bg-surface-2 hover:text-ink"
            aria-label={t.close}
          >
            <X />
          </button>
        </div>

        <div className="flex items-center gap-2 px-5 pt-3" role="tablist">
          {(["ar", "en"] as const).map((l) => (
            <button
              key={l}
              type="button"
              role="tab"
              aria-selected={tab === l}
              disabled={versions !== null && !versions[l]}
              onClick={() => setTab(l)}
              className={`rounded-full border px-3 py-1 text-xs transition-colors disabled:opacity-40 ${
                tab === l ? "border-accent bg-accent-soft text-accent" : "border-line text-muted hover:text-ink"
              }`}
            >
              {l === "ar" ? "العربية" : "English"}
              <span className="ms-1.5 opacity-70">· {l === "ar" ? t.authoritative : t.translation}</span>
            </button>
          ))}
        </div>

        <div className="min-h-0 flex-1 overflow-y-auto px-5 py-4">
          {versions === null ? (
            <div className="space-y-2.5">
              {[92, 100, 85, 96, 60].map((w, i) => (
                <div key={i} className="skeleton h-4" style={{ width: `${w}%` }} />
              ))}
            </div>
          ) : parts ? (
            <div dir={tab === "ar" ? "rtl" : "ltr"} lang={tab} className={`font-read space-y-4 ${tab === "ar" ? "text-[1.1rem] leading-[2.05]" : "text-[1.02rem] leading-8"}`}>
              {parts.map((p) => (
                <p key={p.id} className="whitespace-pre-line">
                  {p.text.replace(/\n\s*\n(\s*\n)+/g, "\n\n")}
                </p>
              ))}
            </div>
          ) : (
            <p className="text-sm text-muted">{t.noCounterpart}</p>
          )}
        </div>

        <div className="flex items-center justify-between gap-3 border-t border-line px-5 py-3 text-xs text-muted">
          <span>{pages}</span>
          <a href={OFFICIAL_URL} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 hover:text-ink">
            {t.officialSource} <External size={13} />
          </a>
        </div>
      </aside>
    </>
  );
}
