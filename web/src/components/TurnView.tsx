"use client";

import { useState } from "react";
import type { Done, Lang, Source } from "@/lib/api";
import { AnswerText } from "./AnswerText";
import { Alert, Check, Copy, SearchOff } from "./Icons";
import { usePrefs } from "./Prefs";

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
}

interface Props {
  turn: TurnState;
  onCite: (chunkId: string) => void;
  onRetry: () => void;
}

/** "المادة (29)\nالإجازة السنوية\n…" -> "الإجازة السنوية" */
function sourceTitle(s: Source): string {
  const [first, second] = s.text.split("\n").map((l) => l.trim());
  return /^(Article|المادة)/i.test(first ?? "") ? (second ?? "") : "";
}

export function TurnView({ turn, onCite, onRetry }: Props) {
  const { t } = usePrefs();
  const lang = turn.done?.language ?? turn.lang ?? "en";
  const dir = lang === "ar" ? "rtl" : "ltr";
  const done = turn.done;
  const abstained = done?.abstained;

  return (
    <article className="rise scroll-mt-20">
      <div className="mb-3 flex items-start gap-3">
        <span className="mt-0.5 shrink-0 rounded-md bg-surface-2 px-2 py-0.5 text-xs font-medium text-muted">
          {t.you}
        </span>
        <div className="min-w-0">
          <h2 dir="auto" className="text-[1.08rem] font-semibold leading-7">
            {turn.question}
          </h2>
          {turn.searchQuery && (
            <p className="mt-0.5 text-xs text-muted" dir="auto">
              {t.searchedAs}: “{turn.searchQuery}”
            </p>
          )}
        </div>
      </div>

      {turn.status === "error" ? (
        <Notice
          tone="danger"
          icon={<Alert />}
          title={turn.error === "busy" ? t.busyTitle : t.errorTitle}
          body={turn.error === "busy" ? t.busyBody : turn.error === "unavailable" ? t.unavailableBody : t.errorBody}
          action={{ label: t.retry, onClick: onRetry }}
        />
      ) : abstained ? (
        <Notice
          tone="muted"
          icon={<SearchOff />}
          title={t.notFoundTitle}
          body={done?.abstain_reason === "low_relevance" ? t.notFoundLow : t.notFoundModel}
        />
      ) : (
        <div className="rounded-2xl border border-line bg-surface px-5 py-4 shadow-card sm:px-6 sm:py-5">
          {turn.status === "searching" ? (
            <Progress label={t.thinking} />
          ) : turn.answer ? (
            <div
              dir={dir}
              lang={lang}
              // Naskh needs a little more size and line height than Latin text.
              className={`font-read ${lang === "ar" ? "text-[1.15rem] leading-[2]" : "text-[1.075rem] leading-[1.8]"}`}
            >
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
            <Progress label={t.writing} />
          )}
          {done && <AnswerMeta done={done} />}
        </div>
      )}

      {turn.sources.length > 0 && !abstained && turn.status !== "error" && (
        <details className="group mt-3">
          <summary className="cursor-pointer list-none text-sm text-muted hover:text-ink [&::-webkit-details-marker]:hidden">
            <span className="inline-flex items-center gap-1.5">
              <span className="inline-block transition-transform group-open:rotate-90 rtl:-scale-x-100">›</span>
              {t.sources(turn.sources.length)}
            </span>
          </summary>
          <ol className="mt-2 grid gap-1.5 sm:grid-cols-2">
            {turn.sources.map((s, i) => (
              <li key={s.id}>
                <button
                  type="button"
                  onClick={() => onCite(s.id)}
                  className="flex w-full items-center gap-2.5 rounded-lg border border-line bg-surface px-3 py-2 text-start text-sm transition-colors hover:border-accent-line"
                >
                  <span className="text-xs tabular-nums text-faint">{i + 1}</span>
                  <span className="min-w-0 flex-1 truncate" dir={s.language === "ar" ? "rtl" : "ltr"}>
                    {s.language === "ar" ? `المادة ${s.article ?? ""}` : `Article ${s.article ?? ""}`}
                    {sourceTitle(s) && <span className="text-muted"> · {sourceTitle(s)}</span>}
                  </span>
                  <span className="rounded bg-surface-2 px-1.5 py-0.5 text-[10px] font-medium uppercase text-muted">
                    {s.language}
                  </span>
                </button>
              </li>
            ))}
          </ol>
        </details>
      )}
    </article>
  );
}

function AnswerMeta({ done }: { done: Done }) {
  const { t } = usePrefs();
  const [copied, setCopied] = useState(false);
  const ok = done.citations.filter((c) => c.valid).length;
  const bad = done.citations.length - ok;
  const secs = (done.latency_ms.total ?? 0) / 1000;
  return (
    <div className="mt-4 flex flex-wrap items-center gap-x-4 gap-y-1.5 border-t border-line pt-3 text-xs text-muted">
      {ok > 0 && (
        <span className="inline-flex items-center gap-1 text-accent">
          <Check size={14} strokeWidth={2.4} /> {t.verified(ok)}
        </span>
      )}
      {bad > 0 && (
        <span className="inline-flex items-center gap-1 text-warn">
          <Alert size={14} /> {t.unverified(bad)}
        </span>
      )}
      <span className="tabular-nums">{t.seconds(secs)}</span>
      <span className="truncate">{done.model}</span>
      <button
        type="button"
        onClick={async () => {
          try {
            await navigator.clipboard.writeText(done.answer);
            setCopied(true);
            setTimeout(() => setCopied(false), 1500);
          } catch {
            // Clipboard blocked: nothing useful to do.
          }
        }}
        className="ms-auto inline-flex items-center gap-1 rounded-md px-1.5 py-0.5 hover:bg-surface-2 hover:text-ink"
      >
        {copied ? <Check size={14} /> : <Copy size={14} />}
        {copied ? t.copied : t.copy}
      </button>
    </div>
  );
}

function Progress({ label }: { label: string }) {
  return (
    <div className="space-y-3" aria-live="polite">
      <p className="text-sm text-muted">{label}</p>
      <div className="space-y-2">
        <div className="skeleton h-3.5 w-[92%]" />
        <div className="skeleton h-3.5 w-[78%]" />
        <div className="skeleton h-3.5 w-[64%]" />
      </div>
    </div>
  );
}

function Notice({
  tone,
  icon,
  title,
  body,
  action,
}: {
  tone: "danger" | "muted";
  icon: React.ReactNode;
  title: string;
  body: string;
  action?: { label: string; onClick: () => void };
}) {
  const color = tone === "danger" ? "border-danger/30 bg-danger-soft text-danger" : "border-line bg-surface-2 text-muted";
  return (
    <div className={`flex items-start gap-3 rounded-2xl border px-5 py-4 ${color}`}>
      <span className="mt-0.5 shrink-0">{icon}</span>
      <div className="min-w-0 flex-1">
        <p className="font-medium text-ink">{title}</p>
        <p className="mt-0.5 text-sm">{body}</p>
      </div>
      {action && (
        <button
          type="button"
          onClick={action.onClick}
          className="shrink-0 rounded-lg border border-current/30 px-3 py-1.5 text-sm font-medium hover:bg-surface"
        >
          {action.label}
        </button>
      )}
    </div>
  );
}
