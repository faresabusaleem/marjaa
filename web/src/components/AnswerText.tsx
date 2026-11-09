"use client";

import type { Citation, Lang, Source } from "@/lib/api";
import { resolveCite, splitBold, splitCitations, type ResolvedCite } from "@/lib/citations";
import { Alert, Check } from "./Icons";
import { usePrefs } from "./Prefs";

interface Props {
  text: string;
  lang: Lang;
  sources: Source[];
  citations: Citation[] | null; // null while streaming (not yet verified)
  streaming: boolean;
  onCite: (chunkId: string) => void;
}

const LIST_ITEM = /^\s*(?:[-*•]|\d+[.)])\s+/;

/** Renders model output: paragraphs, simple lists, **bold**, and citation chips. */
export function AnswerText({ text, lang, sources, citations, streaming, onCite }: Props) {
  // Hide a half-streamed "[Federal Labour La" until its bracket closes.
  let shown = text;
  if (streaming) {
    const open = shown.lastIndexOf("[");
    if (open !== -1 && shown.indexOf("]", open) === -1) shown = shown.slice(0, open);
  }

  const lines = shown.split("\n").filter((l) => l.trim());
  const blocks: { list: boolean; lines: string[] }[] = [];
  for (const line of lines) {
    const list = LIST_ITEM.test(line);
    const prev = blocks.at(-1);
    if (prev && prev.list && list) prev.lines.push(line.replace(LIST_ITEM, ""));
    else blocks.push({ list, lines: [list ? line.replace(LIST_ITEM, "") : line] });
  }

  const renderLine = (line: string, key: string, last: boolean) => (
    <span key={key} className={last && streaming ? "caret" : undefined}>
      {splitCitations(line).map((piece, i) =>
        piece.kind === "text" ? (
          splitBold(piece.text).map((b, j) =>
            b.bold ? <strong key={`${i}-${j}`}>{b.text}</strong> : <span key={`${i}-${j}`}>{b.text}</span>,
          )
        ) : (
          <span key={i} className="whitespace-nowrap">
            {piece.articles.map((n) => (
              <CiteChip
                key={n}
                cite={resolveCite(n, piece.raw, sources, citations, lang)}
                lang={lang}
                raw={piece.raw}
                onCite={onCite}
              />
            ))}
          </span>
        ),
      )}
    </span>
  );

  if (!blocks.length) return <p className={streaming ? "caret" : undefined} />;
  return (
    <div className="space-y-3">
      {blocks.map((block, bi) => {
        const lastBlock = bi === blocks.length - 1;
        return block.list ? (
          <ul key={bi} className="list-disc space-y-1.5 ps-6 marker:text-faint">
            {block.lines.map((l, li) => (
              <li key={li}>{renderLine(l, `${bi}-${li}`, lastBlock && li === block.lines.length - 1)}</li>
            ))}
          </ul>
        ) : (
          <p key={bi}>{block.lines.map((l, li) => renderLine(l, `${bi}-${li}`, lastBlock))}</p>
        );
      })}
    </div>
  );
}

function CiteChip({
  cite,
  lang,
  raw,
  onCite,
}: {
  cite: ResolvedCite;
  lang: Lang;
  raw: string;
  onCite: (chunkId: string) => void;
}) {
  const { t } = usePrefs();
  const label = lang === "ar" ? `المادة ${cite.article}` : `Art. ${cite.article}`;
  const status =
    cite.state === "verified" ? t.verifiedCite : cite.state === "unverified" ? t.unverifiedCite : t.pendingCite;
  const tone =
    cite.state === "unverified"
      ? "border-warn/40 bg-warn-soft text-warn"
      : "border-accent-line bg-accent-soft text-accent hover:border-accent";
  return (
    <button
      type="button"
      disabled={!cite.chunkId}
      onClick={() => cite.chunkId && onCite(cite.chunkId)}
      title={`${raw} — ${status}`}
      aria-label={`${raw}. ${status}`}
      className={`mx-0.5 inline-flex translate-y-[-1px] items-center gap-1 rounded-md border px-1.5 py-px align-baseline font-sans text-[0.78em] font-medium leading-5 transition-colors disabled:cursor-default ${tone}`}
    >
      {cite.state === "verified" && <Check size={12} strokeWidth={2.5} />}
      {cite.state === "unverified" && <Alert size={12} strokeWidth={2.2} />}
      <span dir={lang === "ar" ? "rtl" : "ltr"}>{label}</span>
    </button>
  );
}
