"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { ApiError, ask, type HistoryTurn } from "@/lib/api";
import { EXAMPLES, OFFICIAL_URL } from "@/lib/i18n";
import { Composer } from "./Composer";
import { Languages, Plus, SearchOff, ShieldCheck } from "./Icons";
import { LawPanel } from "./LawPanel";
import { usePrefs } from "./Prefs";
import { type TurnState, TurnView } from "./TurnView";

let counter = 0;
const newId = () => `t${Date.now().toString(36)}${(counter++).toString(36)}`;

export function Chat() {
  const { t } = usePrefs();
  const [turns, setTurns] = useState<TurnState[]>([]);
  const [draft, setDraft] = useState("");
  const [panel, setPanel] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const abortRef = useRef<AbortController | null>(null);
  const lastTurnRef = useRef<HTMLDivElement>(null);

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
            patch(id, () => ({
              status: "writing",
              lang: ev.data.language,
              searchQuery: ev.data.search_query,
              sources: ev.data.sources,
            }));
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
          // Stopped by the user: keep whatever streamed in.
          patch(id, (x) => (x.status === "done" ? {} : { status: x.answer ? "done" : "error", error: x.answer ? null : "error" }));
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
      // Earlier answered turns give follow-ups their context (last three).
      const history = turns
        .filter((x) => x.status === "done" && x.done && !x.done.abstained)
        .slice(-3)
        .map((x) => ({ question: x.question, answer: x.done!.answer }));
      const id = newId();
      setTurns((all) => [
        ...all,
        { id, question, status: "searching", lang: null, searchQuery: null, sources: [], answer: "", done: null, error: null },
      ]);
      setDraft("");
      void run(question, history, id);
    },
    [busy, draft, run, turns],
  );

  const retry = useCallback(
    (id: string) => {
      if (busy) return;
      const index = turns.findIndex((x) => x.id === id);
      if (index === -1) return;
      const history = turns
        .slice(0, index)
        .filter((x) => x.status === "done" && x.done && !x.done.abstained)
        .slice(-3)
        .map((x) => ({ question: x.question, answer: x.done!.answer }));
      patch(id, () => ({ status: "searching", answer: "", done: null, error: null, sources: [], searchQuery: null }));
      void run(turns[index].question, history, id);
    },
    [busy, patch, run, turns],
  );

  const reset = () => {
    abortRef.current?.abort();
    setTurns([]);
    setPanel(null);
    setDraft("");
  };

  // Bring each new question into view.
  const count = turns.length;
  useEffect(() => {
    if (count) lastTurnRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
  }, [count]);

  if (!turns.length) {
    return (
      <main className="mx-auto max-w-3xl px-4 pb-20 pt-12 sm:px-6 sm:pt-20">
        <p className="inline-flex items-center gap-2 rounded-full border border-line bg-surface px-3 py-1 text-xs text-muted">
          <span className="size-1.5 rounded-full bg-accent" />
          {t.eyebrow}
        </p>
        <h1 className="font-read mt-5 text-[2.35rem] font-semibold leading-[1.12] tracking-tight sm:text-[3.1rem]">
          {t.heroTitle}
        </h1>
        <p className="mt-4 max-w-2xl text-[1.05rem] leading-7 text-muted">{t.heroBody}</p>

        <div className="mt-8">
          <Composer
            value={draft}
            onChange={setDraft}
            onSubmit={() => submit()}
            onStop={() => abortRef.current?.abort()}
            busy={busy}
            placeholder={t.placeholder}
            large
            autoFocus
          />
        </div>

        <div className="mt-6">
          <p className="mb-2.5 text-xs font-medium uppercase tracking-wider text-faint">{t.tryOne}</p>
          <div className="grid gap-2 sm:grid-cols-2">
            {EXAMPLES.map((ex) => (
              <button
                key={ex.q}
                type="button"
                onClick={() => submit(ex.q)}
                dir={ex.lang === "ar" ? "rtl" : "ltr"}
                lang={ex.lang}
                className="rounded-xl border border-line bg-surface px-4 py-3 text-start text-[0.95rem] leading-6 text-ink/90 transition-colors hover:border-accent-line hover:bg-accent-soft/40"
              >
                {ex.q}
              </button>
            ))}
          </div>
        </div>

        <ul className="mt-12 grid gap-6 border-t border-line pt-8 sm:grid-cols-3">
          {[
            { icon: <ShieldCheck />, title: t.featCiteTitle, body: t.featCiteBody },
            { icon: <Languages />, title: t.featLangTitle, body: t.featLangBody },
            { icon: <SearchOff />, title: t.featNotFoundTitle, body: t.featNotFoundBody },
          ].map((f) => (
            <li key={f.title}>
              <span className="grid size-9 place-items-center rounded-lg bg-accent-soft text-accent">{f.icon}</span>
              <p className="mt-3 font-medium">{f.title}</p>
              <p className="mt-1 text-sm leading-6 text-muted">{f.body}</p>
            </li>
          ))}
        </ul>

        <Disclaimer />
      </main>
    );
  }

  return (
    <div className="mx-auto max-w-6xl px-4 sm:px-6">
      <div className={`grid gap-8 ${panel ? "lg:grid-cols-[minmax(0,1fr)_400px]" : ""}`}>
        <main className={`min-w-0 pb-40 pt-8 ${panel ? "" : "mx-auto w-full max-w-3xl"}`}>
          <div className="space-y-10">
            {turns.map((turn, i) => (
              <div key={turn.id} ref={i === turns.length - 1 ? lastTurnRef : undefined}>
                <TurnView turn={turn} onCite={setPanel} onRetry={() => retry(turn.id)} />
              </div>
            ))}
          </div>
          <Disclaimer />
        </main>
        {panel && (
          <div className="lg:pt-8">
            <LawPanel chunkId={panel} onClose={() => setPanel(null)} />
          </div>
        )}
      </div>

      <div className="pointer-events-none fixed inset-x-0 bottom-0 z-20 bg-gradient-to-t from-bg via-bg/95 to-transparent pb-4 pt-10">
        <div className={`pointer-events-auto mx-auto flex items-end gap-2 px-4 sm:px-6 ${panel ? "max-w-6xl lg:pe-[calc(400px+3.5rem)]" : "max-w-3xl"}`}>
          <button
            type="button"
            onClick={reset}
            className="mb-1 grid size-10 shrink-0 place-items-center rounded-xl border border-line bg-surface text-muted shadow-card hover:text-ink"
            aria-label={t.newChat}
            title={t.newChat}
          >
            <Plus />
          </button>
          <div className="min-w-0 flex-1">
            <Composer
              value={draft}
              onChange={setDraft}
              onSubmit={() => submit()}
              onStop={() => abortRef.current?.abort()}
              busy={busy}
              placeholder={t.followUpPlaceholder}
            />
          </div>
        </div>
      </div>
    </div>
  );
}

function Disclaimer() {
  const { t } = usePrefs();
  return (
    <p className="mt-12 text-xs leading-5 text-faint">
      {t.disclaimer}{" "}
      <a href={OFFICIAL_URL} target="_blank" rel="noreferrer" className="underline decoration-line underline-offset-2 hover:text-muted">
        uaelegislation.gov.ae
      </a>
    </p>
  );
}
