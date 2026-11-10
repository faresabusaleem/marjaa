"use client";

import { Check, ChevronDown, CircleAlert, Clock, Copy, Link2, RotateCcw, SearchX, ShieldCheck, TriangleAlert } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import type { Done, Lang, Source } from "@/lib/api";
import { localePath } from "@/lib/locale";
import { modelName } from "@/lib/results";
import { SaduLoader } from "../brand/Logo";
import { useLang, useT } from "../site/LangProvider";
import { AnswerText } from "./AnswerText";

export interface TurnState {
  id: string;
  question: string;
  status: "searching" | "writing" | "done" | "error";
  lang: Lang | null;
  searchQuery: string | null;
  sources: Source[];
  answer: string;
  done: Done | null;
  error: "busy" | "unavailable" | "error" | null;
  stopped?: boolean;
}

interface Props {
  turn: TurnState;
  onCite: (chunkId: string, trigger: HTMLElement) => void;
  onRetry: () => void;
  canRetry: boolean;
}

/** "Article (29)\nAnnual leave\n…" -> "Annual leave" */
function sourceTitle(s: Source): string {
  const [first, second] = s.text.split("\n").map((l) => l.trim());
  return /^(Article|المادة)/i.test(first ?? "") ? (second ?? "") : "";
}

const same = (a: string, b: string) => a.trim().replace(/[?؟.]+$/, "").toLowerCase() === b.trim().replace(/[?؟.]+$/, "").toLowerCase();

export function TurnView({ turn, onCite, onRetry, canRetry }: Props) {
  const t = useT();
  const lang = turn.done?.language ?? turn.lang ?? "en";
  const done = turn.done;
  const abstained = done?.abstained;
  const showQuery = turn.searchQuery && !same(turn.searchQuery, turn.question);

  return (
    <article className="enter scroll-mt-24 border-b border-line py-10 first:pt-2 last:border-b-0" aria-busy={turn.status === "searching" || turn.status === "writing"}>
      <h2 dir="auto" className="text-h3 font-semibold text-ink">
        {turn.question}
      </h2>
      {showQuery && (
        <p className="mt-1.5 text-caption text-ink-muted">
          {t.turn.searchedFor}: <bdi dir="auto">{turn.searchQuery}</bdi>
        </p>
      )}

      <div className="mt-5">
        {turn.status === "error" ? (
          turn.error === "busy" ? (
            <Notice tone="warn" icon={<Clock size={18} strokeWidth={1.75} />} title={t.turn.busyTitle} body={t.turn.busyBody}>
              {canRetry && <RetryButton onClick={onRetry} label={t.turn.retry} />}
            </Notice>
          ) : (
            <Notice
              tone="danger"
              icon={<CircleAlert size={18} strokeWidth={1.75} />}
              title={t.turn.errorTitle}
              body={turn.error === "unavailable" ? t.turn.unavailableBody : t.turn.errorBody}
            >
              {canRetry && <RetryButton onClick={onRetry} label={t.turn.retry} />}
            </Notice>
          )
        ) : abstained ? (
          <NotFound reason={done?.abstain_reason ?? null} />
        ) : turn.status === "searching" ? (
          <SaduLoader label={t.turn.finding} />
        ) : turn.answer ? (
          <div dir={lang === "ar" ? "rtl" : "ltr"} lang={lang} className="reading max-w-[68ch] text-ink">
            <AnswerText
              text={turn.answer}
              lang={lang}
              sources={turn.sources}
              citations={done?.citations ?? null}
              streaming={turn.status === "writing"}
              onCite={onCite}
            />
          </div>
        ) : (
          <SaduLoader label={t.turn.writing} />
        )}
      </div>

      {done && !abstained && <AnswerMeta done={done} question={turn.question} stopped={turn.stopped} />}

      {turn.sources.length > 0 && !abstained && turn.status !== "error" && (
        <details className="group mt-5">
          <summary className="inline-flex cursor-pointer list-none items-center gap-1.5 rounded-sm text-small text-ink-muted hover:text-ink [&::-webkit-details-marker]:hidden">
            <ChevronDown size={16} strokeWidth={1.75} className="transition-transform group-open:rotate-180" aria-hidden />
            {t.turn.consulted(turn.sources.length)}
          </summary>
          <ul className="mt-3 border-t border-line">
            {turn.sources.map((s) => (
              <li key={s.id}>
                <button
                  type="button"
                  onClick={(e) => onCite(s.id, e.currentTarget)}
                  className="grid w-full grid-cols-[4.75rem_minmax(0,1fr)_auto] items-baseline gap-3 border-b border-line py-2.5 text-start text-small transition-colors hover:bg-surface"
                >
                  <span className={`tabular text-ink-muted ${s.language === "en" ? "font-mono text-caption" : ""}`} dir={s.language === "ar" ? "rtl" : "ltr"}>
                    {s.language === "ar" ? `المادة ${s.article ?? ""}` : `Art. ${s.article ?? ""}`}
                  </span>
                  <span className="truncate text-ink" dir={s.language === "ar" ? "rtl" : "ltr"} lang={s.language}>
                    {sourceTitle(s)}
                  </span>
                  <span className="text-caption uppercase text-ink-muted">{s.language}</span>
                </button>
              </li>
            ))}
          </ul>
        </details>
      )}
    </article>
  );
}

function AnswerMeta({ done, question, stopped }: { done: Done; question: string; stopped?: boolean }) {
  const t = useT();
  const lang = useLang();
  const [copied, setCopied] = useState<"answer" | "link" | null>(null);
  const ok = done.citations.filter((c) => c.valid).length;
  const bad = done.citations.length - ok;
  const secs = (done.latency_ms.total ?? 0) / 1000;

  const permalink = () => `${location.origin}${localePath(lang, "/")}?q=${encodeURIComponent(question)}`;
  const copy = async (what: "answer" | "link") => {
    const text = what === "answer" ? `${question}\n\n${done.answer}\n\n${t.turn.copyFooter}: ${permalink()}` : permalink();
    try {
      await navigator.clipboard.writeText(text);
      setCopied(what);
      setTimeout(() => setCopied(null), 1600);
    } catch {
      // Clipboard blocked: nothing useful to do.
    }
  };

  return (
    <div className="mt-6 flex flex-wrap items-center gap-x-5 gap-y-2 text-caption text-ink-muted">
      {ok > 0 && (
        <span className="inline-flex items-center gap-1.5 font-medium text-accent">
          <ShieldCheck size={15} strokeWidth={1.75} aria-hidden /> {t.turn.verified(ok)}
        </span>
      )}
      {bad > 0 && (
        <span className="inline-flex items-center gap-1.5 font-medium text-warn">
          <TriangleAlert size={15} strokeWidth={1.75} aria-hidden /> {t.turn.unverified(bad)}
        </span>
      )}
      {stopped ? <span>{t.turn.stopped}</span> : <span className="tabular">{t.turn.seconds(secs)}</span>}
      <span dir="ltr">{modelName(`${done.provider}:${done.model}`)}</span>
      <span className="ms-auto flex gap-1" aria-live="polite">
        <MetaButton onClick={() => copy("answer")} icon={copied === "answer" ? <Check size={14} /> : <Copy size={14} strokeWidth={1.75} />}>
          {copied === "answer" ? t.turn.copied : t.turn.copy}
        </MetaButton>
        <MetaButton onClick={() => copy("link")} icon={copied === "link" ? <Check size={14} /> : <Link2 size={14} strokeWidth={1.75} />}>
          {copied === "link" ? t.turn.linkCopied : t.turn.copyLink}
        </MetaButton>
      </span>
    </div>
  );
}

function MetaButton({ onClick, icon, children }: { onClick: () => void; icon: React.ReactNode; children: React.ReactNode }) {
  return (
    <button type="button" onClick={onClick} className="inline-flex items-center gap-1.5 rounded-md px-2 py-1.5 text-ink-muted transition-colors hover:bg-surface hover:text-ink">
      <span aria-hidden>{icon}</span>
      {children}
    </button>
  );
}

function NotFound({ reason }: { reason: "low_relevance" | "model" | null }) {
  const t = useT();
  const lang = useLang();
  return (
    <div className="flex max-w-[68ch] gap-4 rounded-lg bg-surface p-5 sm:p-6">
      <SearchX size={22} strokeWidth={1.5} className="mt-0.5 shrink-0 text-brand-sea" aria-hidden />
      <div>
        <p className="font-semibold text-ink">{t.turn.notFoundTitle}</p>
        <p className="mt-1.5 text-small text-ink-muted">{reason === "low_relevance" ? t.turn.notFoundLow : t.turn.notFoundModel}</p>
        <Link href={localePath(lang, "/library")} className="link mt-3 inline-block text-small">
          {t.turn.browseLaw}
        </Link>
      </div>
    </div>
  );
}

function Notice({
  tone,
  icon,
  title,
  body,
  children,
}: {
  tone: "warn" | "danger";
  icon: React.ReactNode;
  title: string;
  body: string;
  children?: React.ReactNode;
}) {
  const colors = tone === "warn" ? "bg-warn-subtle text-warn" : "bg-danger-subtle text-danger";
  return (
    <div role="alert" className={`flex max-w-[68ch] flex-wrap items-start gap-x-4 gap-y-3 rounded-lg p-5 sm:flex-nowrap sm:p-6 ${colors}`}>
      <span className="mt-0.5 shrink-0" aria-hidden>
        {icon}
      </span>
      <div className="min-w-0 flex-1">
        <p className="font-semibold">{title}</p>
        <p className="mt-1 text-small">{body}</p>
      </div>
      {children}
    </div>
  );
}

function RetryButton({ onClick, label }: { onClick: () => void; label: string }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="inline-flex shrink-0 items-center gap-2 rounded-md border border-current px-3.5 py-2 text-small font-medium transition-colors hover:bg-bg"
    >
      <RotateCcw size={15} strokeWidth={1.75} aria-hidden />
      {label}
    </button>
  );
}
