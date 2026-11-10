"use client";

import { ArrowLeft, ArrowRight, ArrowUpRight, Plus } from "lucide-react";
import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import { ApiError, ask, type HistoryTurn } from "@/lib/api";
import { EXAMPLES, officialUrl } from "@/lib/i18n";
import { localePath } from "@/lib/locale";
import { useLang, useT } from "../site/LangProvider";
import { Composer } from "./Composer";
import { LawPanel } from "./LawPanel";
import { type TurnState, TurnView } from "./TurnView";

export interface Headline {
  questions: number;
  articles: number;
  recall5: string;
  citationValidity: string;
  abstention: string;
}

const STORE = "marjaa.conversation";
let counter = 0;
const newId = () => `t${Date.now().toString(36)}${(counter++).toString(36)}`;

/** Earlier answered turns give a follow-up its context (the last three). */
const historyOf = (turns: TurnState[]): HistoryTurn[] =>
  turns
    .filter((x) => x.status === "done" && x.done && !x.done.abstained)
    .slice(-3)
    .map((x) => ({ question: x.question, answer: x.done!.answer }));

function useWide() {
  const [wide, setWide] = useState(false);
  useEffect(() => {
    const media = matchMedia("(min-width: 1024px)");
    const update = () => setWide(media.matches);
    update();
    media.addEventListener("change", update);
    return () => media.removeEventListener("change", update);
  }, []);
  return wide;
}

export function Chat({ headline }: { headline: Headline }) {
  const t = useT();
  const wide = useWide();
  const [turns, setTurns] = useState<TurnState[]>([]);
  const [draft, setDraft] = useState("");
  const [panel, setPanel] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const abortRef = useRef<AbortController | null>(null);
  const triggerRef = useRef<HTMLElement | null>(null);
  const lastTurnRef = useRef<HTMLDivElement>(null);
  const started = useRef(false);

  const patch = useCallback((id: string, update: (t: TurnState) => Partial<TurnState>) => {
    setTurns((all) => all.map((x) => (x.id === id ? { ...x, ...update(x) } : x)));
  }, []);

  const run = useCallback(
    async (question: string, history: HistoryTurn[], id: string) => {
      const controller = new AbortController();
      abortRef.current = controller;
      setBusy(true);
      try {
        for await (const ev of ask(question, history, controller.signal)) {
          if (ev.event === "sources") {
            patch(id, () => ({ status: "writing", lang: ev.data.language, searchQuery: ev.data.search_query, sources: ev.data.sources }));
          } else if (ev.event === "token") {
            patch(id, (x) => ({ answer: x.answer + ev.data.text }));
          } else if (ev.event === "done") {
            patch(id, () => ({ status: "done", done: ev.data, answer: ev.data.answer }));
          } else if (ev.event === "error") {
            patch(id, () => ({ status: "error", error: ev.data.code }));
          }
        }
      } catch (err) {
        if (controller.signal.aborted) {
          // Stopped: keep whatever streamed in.
          patch(id, (x) => (x.status === "done" ? {} : x.answer ? { status: "done", stopped: true } : { status: "error", error: "error" }));
        } else {
          patch(id, () => ({ status: "error", error: err instanceof ApiError ? err.code : "error" }));
        }
      } finally {
        setTurns((all) =>
          all.map((x) => (x.id === id && (x.status === "searching" || x.status === "writing") ? { ...x, status: "error", error: "error" } : x)),
        );
        abortRef.current = null;
        setBusy(false);
      }
    },
    [patch],
  );

  const submit = useCallback(
    (text?: string) => {
      const question = (text ?? draft).trim();
      if (question.length < 2 || busy) return;
      const id = newId();
      setTurns((all) => [
        ...all,
        { id, question, status: "searching", lang: null, searchQuery: null, sources: [], answer: "", done: null, error: null },
      ]);
      setDraft("");
      void run(question, historyOf(turns), id);
    },
    [busy, draft, run, turns],
  );

  const retry = useCallback(
    (id: string) => {
      const index = turns.findIndex((x) => x.id === id);
      if (busy || index === -1) return;
      patch(id, () => ({ status: "searching", answer: "", done: null, error: null, sources: [], searchQuery: null, stopped: false }));
      void run(turns[index].question, historyOf(turns.slice(0, index)), id);
    },
    [busy, patch, run, turns],
  );

  const reset = () => {
    abortRef.current?.abort();
    setTurns([]);
    setPanel(null);
    setDraft("");
  };

  const openPanel = useCallback((chunkId: string, trigger: HTMLElement) => {
    triggerRef.current = trigger;
    setPanel(chunkId);
  }, []);
  const closePanel = useCallback(() => {
    setPanel(null);
    triggerRef.current?.focus({ preventScroll: true });
  }, []);

  // Restore the conversation (it survives a language switch or a reload in this
  // tab), then ask the question in ?q= if there is one.
  useEffect(() => {
    if (started.current) return;
    started.current = true;
    let restored: TurnState[] = [];
    try {
      restored = JSON.parse(sessionStorage.getItem(STORE) ?? "[]");
    } catch {
      restored = [];
    }
    if (restored.length) setTurns(restored);
    const params = new URLSearchParams(location.search);
    const q = params.get("q")?.trim();
    if (q) {
      history.replaceState(null, "", location.pathname);
      if (restored.at(-1)?.question !== q) {
        const id = newId();
        setTurns([...restored, { id, question: q, status: "searching", lang: null, searchQuery: null, sources: [], answer: "", done: null, error: null }]);
        void run(q, historyOf(restored), id);
      }
    }
  }, [run]);

  useEffect(() => {
    if (!started.current) return;
    try {
      const settled = turns.filter((x) => x.status === "done" || x.status === "error");
      sessionStorage.setItem(STORE, JSON.stringify(settled));
    } catch {
      // Storage blocked: the conversation just won't survive a reload.
    }
  }, [turns]);

  // Bring each new question into view.
  const count = turns.length;
  useEffect(() => {
    if (count > 1) lastTurnRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
  }, [count]);

  if (!turns.length) return <Welcome headline={headline} draft={draft} setDraft={setDraft} onAsk={submit} busy={busy} />;

  const side = panel !== null && wide;
  return (
    <div className="mx-auto w-full max-w-[76rem] flex-1 px-5 sm:px-8">
      <div className={side ? "grid grid-cols-[minmax(0,1fr)_25rem] gap-10 xl:grid-cols-[minmax(0,1fr)_28rem] xl:gap-14" : ""}>
        <div className={`flex min-h-[70dvh] min-w-0 flex-col ${side ? "" : "mx-auto max-w-[46rem]"}`}>
          <div className="flex-1 pt-8">
            {turns.map((turn, i) => (
              <div key={turn.id} ref={i === turns.length - 1 ? lastTurnRef : undefined}>
                <TurnView turn={turn} onCite={openPanel} onRetry={() => retry(turn.id)} canRetry={!busy} />
              </div>
            ))}
          </div>
          <div className="sticky bottom-0 z-10 -mx-5 bg-bg px-5 pb-5 pt-3 sm:-mx-8 sm:px-8">
            <div className="flex items-end gap-2">
              <button
                type="button"
                onClick={reset}
                aria-label={t.ask.newQuestion}
                title={t.ask.newQuestion}
                className="inline-flex h-14 shrink-0 items-center gap-2 rounded-lg border border-line-strong px-3.5 text-small font-medium text-ink-muted transition-colors hover:bg-surface hover:text-ink"
              >
                <Plus size={18} strokeWidth={1.75} aria-hidden />
                <span className="hidden sm:inline">{t.ask.newQuestion}</span>
              </button>
              <div className="min-w-0 flex-1">
                <Composer
                  value={draft}
                  onChange={setDraft}
                  onSubmit={() => submit()}
                  onStop={() => abortRef.current?.abort()}
                  busy={busy}
                  placeholder={t.ask.followUp}
                />
              </div>
            </div>
          </div>
        </div>
        {side && (
          <div className="pt-8">
            <LawPanel chunkId={panel} onClose={closePanel} wide />
          </div>
        )}
      </div>
      {panel !== null && !wide && <LawPanel chunkId={panel} onClose={closePanel} wide={false} />}
    </div>
  );
}

function Welcome({
  headline,
  draft,
  setDraft,
  onAsk,
  busy,
}: {
  headline: Headline;
  draft: string;
  setDraft: (v: string) => void;
  onAsk: (q?: string) => void;
  busy: boolean;
}) {
  const t = useT();
  const lang = useLang();
  const groups = [
    { label: t.ask.examplesEn, lang: "en" as const },
    { label: t.ask.examplesAr, lang: "ar" as const },
  ];
  return (
    <div className="mx-auto w-full max-w-[76rem] px-5 pb-24 pt-14 sm:px-8 sm:pt-20 lg:pb-32 lg:pt-24">
      <div className="grid gap-x-10 gap-y-16 lg:grid-cols-12">
        <div className="lg:col-span-8">
          <h1
            className={`text-display font-semibold text-ink ${lang === "ar" ? "font-display-ar font-bold" : "max-w-[13ch]"}`}
          >
            {t.ask.title}
          </h1>
          <p className="mt-6 max-w-[38rem] text-lead text-ink">{t.ask.lead}</p>

          <div className="mt-10">
            <Composer value={draft} onChange={setDraft} onSubmit={() => onAsk()} onStop={() => undefined} busy={busy} placeholder={t.ask.placeholder} large autoFocus />
          </div>

          <section className="mt-14" aria-labelledby="examples">
            <h2 id="examples" className="text-h3 font-semibold">
              {t.ask.examples}
            </h2>
            <div className="mt-5 grid gap-x-10 gap-y-8 md:grid-cols-2">
              {groups.map((g) => (
                <div key={g.lang}>
                  <p className="text-small text-ink-muted">{g.label}</p>
                  <ul className="mt-2 border-t border-line">
                    {EXAMPLES.filter((ex) => ex.lang === g.lang).map((ex) => (
                      <li key={ex.q}>
                        <button
                          type="button"
                          onClick={() => onAsk(ex.q)}
                          dir={ex.lang === "ar" ? "rtl" : "ltr"}
                          lang={ex.lang}
                          className="group flex w-full items-start justify-between gap-4 border-b border-line py-3.5 text-start text-body leading-snug text-ink transition-colors hover:text-accent"
                        >
                          <span>
                            {ex.q}
                            {ex.outOfScope && (
                              <span dir={lang === "ar" ? "rtl" : "ltr"} lang={lang} className="mt-1 block text-caption text-ink-muted">
                                {t.ask.outOfScope}
                              </span>
                            )}
                          </span>
                          {/* Points along the question's own direction, not the page's. */}
                          {ex.lang === "ar" ? (
                            <ArrowLeft size={18} strokeWidth={1.75} className="mt-0.5 shrink-0 text-ink-muted transition-transform group-hover:-translate-x-0.5 group-hover:text-accent" aria-hidden />
                          ) : (
                            <ArrowRight size={18} strokeWidth={1.75} className="mt-0.5 shrink-0 text-ink-muted transition-transform group-hover:translate-x-0.5 group-hover:text-accent" aria-hidden />
                          )}
                        </button>
                      </li>
                    ))}
                  </ul>
                </div>
              ))}
            </div>
          </section>
        </div>

        <aside className="lg:col-span-4 lg:pt-4" aria-label={t.ask.sourceTitle}>
          <div className="rounded-lg bg-surface p-6 sm:p-7">
            <h2 className="text-small font-semibold text-ink-muted">{t.ask.sourceTitle}</h2>
            <p className="mt-3 text-lead font-medium leading-snug text-ink">{t.ask.sourceName}</p>
            <p className="mt-3 text-small text-ink-muted">{t.ask.sourceBody(headline.articles)}</p>
            <div className="mt-5 flex flex-wrap gap-x-5 gap-y-2 text-small">
              <Link href={localePath(lang, "/library")} className="link">
                {t.ask.readLaw}
              </Link>
              <a href={officialUrl(lang)} target="_blank" rel="noreferrer" className="link inline-flex items-center gap-0.5">
                {t.ask.official}
                <ArrowUpRight size={14} strokeWidth={1.75} className="rtl:-scale-x-100" aria-hidden />
              </a>
            </div>

            <h2 className="mt-8 border-t border-line pt-6 text-small font-semibold text-ink-muted">{t.ask.measuredTitle(headline.questions)}</h2>
            <dl className="mt-5 space-y-5">
              {[
                { value: headline.recall5, label: t.ask.statRecall },
                { value: headline.citationValidity, label: t.ask.statCitations },
                { value: headline.abstention, label: t.ask.statAbstain },
              ].map((s) => (
                <div key={s.label} className="flex flex-col-reverse">
                  <dt className="mt-0.5 text-small text-ink-muted">{s.label}</dt>
                  <dd className="tabular text-h2 font-semibold text-ink">
                    <bdi dir="ltr">{s.value}</bdi>
                  </dd>
                </div>
              ))}
            </dl>
            <Link href={localePath(lang, "/how-it-works")} className="link mt-6 inline-block text-small">
              {t.ask.howMeasured}
            </Link>
          </div>
        </aside>
      </div>
    </div>
  );
}
