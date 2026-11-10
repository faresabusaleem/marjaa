"use client";

import { Check, TriangleAlert } from "lucide-react";
import type { Citation, Lang, Source } from "@/lib/api";
import { resolveCite, splitBold, splitCitations, type ResolvedCite } from "@/lib/citations";
import { STRINGS } from "@/lib/i18n";
import { useT } from "../site/LangProvider";

interface Props {
  text: string;
  lang: Lang;
  sources: Source[];
  citations: Citation[] | null; // null while streaming (not yet verified)
  streaming: boolean;
  onCite: (chunkId: string, trigger: HTMLElement) => void;
}

const LIST_ITEM = /^\s*(?:[-*•]|\d+[.)])\s+/;

/** Model output: paragraphs, simple lists, **bold**, and citation chips. */
export function AnswerText({ text, lang, sources, citations, streaming, onCite }: Props) {
  // Hide a half-streamed "[Federal Labour La" until its bracket closes.
  let shown = text;
  if (streaming) {
    const open = shown.lastIndexOf("[");
    if (open !== -1 && shown.indexOf("]", open) === -1) shown = shown.slice(0, open);
  }

  const blocks: { list: boolean; lines: string[] }[] = [];
  for (const line of shown.split("\n").filter((l) => l.trim())) {
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
            b.bold ? (
              <strong key={`${i}-${j}`} className="font-semibold">
                {b.text}
              </strong>
            ) : (
              <span key={`${i}-${j}`}>{b.text}</span>
            ),
          )
        ) : (
          <span key={i} className="whitespace-nowrap">
            {piece.articles.map((n) => (
              <CiteChip key={n} cite={resolveCite(n, piece.raw, sources, citations, lang)} lang={lang} onCite={onCite} />
            ))}
          </span>
        ),
      )}
    </span>
  );

  if (!blocks.length) return <p className={streaming ? "caret" : undefined} />;
  return (
    <div className="space-y-4">
      {blocks.map((block, bi) => {
        const lastBlock = bi === blocks.length - 1;
        return block.list ? (
          <ul key={bi} className="list-disc space-y-2 ps-6 marker:text-brand-sea">
            {block.lines.map((l, li) => (
              <li key={li} className="ps-1">
                {renderLine(l, `${bi}-${li}`, lastBlock && li === block.lines.length - 1)}
              </li>
            ))}
          </ul>
        ) : (
          <p key={bi}>{block.lines.map((l, li) => renderLine(l, `${bi}-${li}`, lastBlock))}</p>
        );
      })}
    </div>
  );
}

/** A citation set like a legal reference: "Art. 29" / "المادة 29", its check shown on the chip. */
function CiteChip({ cite, lang, onCite }: { cite: ResolvedCite; lang: Lang; onCite: Props["onCite"] }) {
  const t = useT();
  // The chip reads in the answer's language, whatever the interface language.
  const label = STRINGS[lang].turn.citeLabel(cite.article);
  const status =
    cite.state === "verified"
      ? t.turn.citeVerified(cite.article)
      : cite.state === "unverified"
        ? t.turn.citeUnverified(cite.article)
        : t.turn.citePending(cite.article);
  const tone =
    cite.state === "unverified"
      ? "border-dashed border-warn-line bg-warn-subtle text-warn"
      : cite.state === "verified"
        ? "border-accent-line bg-accent-subtle text-accent hover:border-brand-sea"
        : "border-line bg-surface text-ink-muted";
  return (
    <button
      type="button"
      disabled={!cite.chunkId}
      onClick={(e) => cite.chunkId && onCite(cite.chunkId, e.currentTarget)}
      title={status}
      aria-label={status}
      className={`mx-0.5 inline-flex -translate-y-px items-center gap-1 rounded-sm border px-1.5 align-baseline text-[0.8em] font-medium leading-[1.55] transition-colors disabled:cursor-default ${
        lang === "en" ? "font-mono tracking-tight" : "font-sans"
      } ${tone}`}
    >
      {cite.state === "verified" && <Check size={11} strokeWidth={2.5} aria-hidden />}
      {cite.state === "unverified" && <TriangleAlert size={11} strokeWidth={2.25} aria-hidden />}
      <span dir={lang === "ar" ? "rtl" : "ltr"} className="tabular">
        {label}
      </span>
    </button>
  );
}
