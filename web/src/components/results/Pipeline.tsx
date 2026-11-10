import { STRINGS } from "@/lib/i18n";
import type { Lang } from "@/lib/locale";

// The pipeline as a flow diagram in the brand: stages on Sand, connectors in
// the strong line colour, and inverted Sadu triangles as the arrowheads.
// It is an ordered list underneath, so screen readers get the stages in order.

type StepKey = keyof (typeof STRINGS)["en"]["how"]["steps"];

function Node({ k, lang, variant = "plain", tag }: { k: StepKey; lang: Lang; variant?: "plain" | "gate" | "end" | "optional"; tag?: string }) {
  const [title, body] = STRINGS[lang].how.steps[k];
  const style = {
    plain: "bg-surface",
    gate: "bg-surface outline outline-2 -outline-offset-2 outline-brand-sea",
    end: "bg-accent-subtle",
    optional: "bg-bg outline outline-1 -outline-offset-1 outline-dashed outline-line-strong",
  }[variant];
  return (
    <div className={`rounded-md px-5 py-4 ${style}`}>
      <p className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1">
        <span className="font-semibold text-ink">{title}</span>
        {tag && <span className="text-caption text-ink-muted">{tag}</span>}
      </p>
      <p className="mt-1 text-small text-ink-muted">{body}</p>
    </div>
  );
}

/** A vertical connector ending in an inverted Sadu triangle. */
function Down({ label }: { label?: string }) {
  return (
    <div className="flex flex-col items-center py-1" aria-hidden="true">
      <span className="h-5 w-0.5 bg-line-strong" />
      {label && <span className="py-1 text-caption text-ink-muted">{label}</span>}
      {label && <span className="h-2 w-0.5 bg-line-strong" />}
      <svg width="12" height="11" viewBox="0 0 20 18" className="fill-brand-gold">
        <polygon points="0,0 20,0 10,18" />
      </svg>
    </div>
  );
}

/** Fork from one stage into two, or join two back into one. */
function Bracket({ join }: { join?: boolean }) {
  return (
    <div className="relative h-6" aria-hidden="true">
      <span
        className={`absolute inset-x-1/4 h-3 border-line-strong ${join ? "top-0 rounded-b-sm border-x-2 border-b-2" : "bottom-0 rounded-t-sm border-x-2 border-t-2"}`}
      />
      <span className={`absolute start-1/2 h-3 w-0.5 -translate-x-1/2 bg-line-strong rtl:translate-x-1/2 ${join ? "bottom-0" : "top-0"}`} />
    </div>
  );
}

export function Pipeline({ lang }: { lang: Lang }) {
  const t = STRINGS[lang].how;
  return (
    <figure className="mx-auto max-w-[44rem]">
      <ol className="list-none">
        <li>
          <div className="mx-auto max-w-sm">
            <Node k="question" lang={lang} />
          </div>
          <Bracket />
        </li>
        <li>
          <ul className="grid list-none grid-cols-2 gap-3 sm:gap-4">
            <li>
              <Node k="bm25" lang={lang} />
            </li>
            <li>
              <Node k="dense" lang={lang} />
            </li>
          </ul>
          <Bracket join />
          <div className="flex justify-center" aria-hidden="true">
            <svg width="12" height="11" viewBox="0 0 20 18" className="fill-brand-gold">
              <polygon points="0,0 20,0 10,18" />
            </svg>
          </div>
        </li>
        <li className="mx-auto max-w-sm">
          <Node k="fusion" lang={lang} />
          <Down />
        </li>
        <li className="mx-auto max-w-sm">
          <Node k="rerank" lang={lang} variant="optional" tag={t.localOnly} />
          <Down />
        </li>
        <li className="relative mx-auto max-w-sm">
          <Node k="gate" lang={lang} variant="gate" />
          {/* The branch: beside the gate on wide screens, under it on phones. */}
          <div className="mt-3 flex items-stretch gap-3 lg:absolute lg:start-full lg:top-1/2 lg:mt-0 lg:w-[17rem] lg:-translate-y-1/2 lg:gap-2 lg:ps-0">
            <div className="hidden w-20 shrink-0 flex-col items-center justify-center lg:flex" aria-hidden="true">
              <span className="whitespace-nowrap text-caption text-ink-muted">{t.fails}</span>
              <span className="flex w-full items-center">
                <span className="h-0.5 flex-1 bg-line-strong" />
                <svg width="11" height="12" viewBox="0 0 18 20" className="shrink-0 fill-brand-gold rtl:-scale-x-100">
                  <polygon points="0,0 18,10 0,20" />
                </svg>
              </span>
            </div>
            <div className="flex-1 ps-6 lg:ps-0">
              <p className="mb-1 text-caption text-ink-muted lg:hidden">{t.fails}</p>
              <Node k="notFound" lang={lang} variant="end" />
            </div>
          </div>
          <Down label={t.passes} />
        </li>
        <li className="mx-auto max-w-sm">
          <Node k="answer" lang={lang} />
          <Down />
        </li>
        <li className="mx-auto max-w-sm">
          <Node k="check" lang={lang} variant="end" />
        </li>
      </ol>
    </figure>
  );
}
