import { ArrowUpRight } from "lucide-react";
import type { Metadata } from "next";
import { BarChart } from "@/components/results/BarChart";
import { Pipeline } from "@/components/results/Pipeline";
import { REPO_URL, STRINGS } from "@/lib/i18n";
import { isLang } from "@/lib/locale";
import { pageMetadata } from "@/lib/metadata";
import {
  answersHosted,
  answersLocal,
  embedderName,
  judgeAgreement,
  type ModeKey,
  modelName,
  pct,
  promptAblation,
  retrievalHosted,
  retrievalLocal,
  secs,
  testset,
} from "@/lib/results";

export async function generateMetadata({ params }: PageProps<"/[lang]/how-it-works">): Promise<Metadata> {
  const { lang: l } = await params;
  const lang = isLang(l) ? l : "en";
  return pageMetadata(lang, "/how-it-works", STRINGS[lang].how.title, STRINGS[lang].how.lead);
}

function Section({ id, title, lead, children }: { id: string; title: string; lead?: string; children: React.ReactNode }) {
  return (
    <section aria-labelledby={id} className="mt-28 lg:mt-40">
      <div className="max-w-3xl">
        <h2 id={id} className="text-h2 font-semibold text-ink">
          {title}
        </h2>
        {lead && <p className="mt-4 text-lead text-ink">{lead}</p>}
      </div>
      <div className="mt-10">{children}</div>
    </section>
  );
}

export default async function HowItWorks({ params }: PageProps<"/[lang]/how-it-works">) {
  const { lang: l } = await params;
  const lang = isLang(l) ? l : "en";
  const t = STRINGS[lang].how;
  const dash = t.notMeasured;
  const lm = retrievalLocal.modes;
  const hm = retrievalHosted?.modes;
  const local = lm.hybrid_rerank!;
  const hosted = hm?.hybrid;
  const s = (ms: number | null | undefined) => {
    const v = secs(ms);
    return v === null ? dash : STRINGS[lang].turn.seconds(Number(v));
  };
  const p = (v: number | null | undefined, digits = 1) => pct(v, digits) ?? dash;

  const rows: { label: string; local: string; hosted: string }[] = [
    { label: t.rows.embeddings, local: embedderName(retrievalLocal.meta.embedder), hosted: retrievalHosted ? embedderName(retrievalHosted.meta.embedder) : dash },
    { label: t.rows.reranker, local: "BGE reranker v2-m3", hosted: t.noReranker },
    { label: t.rows.generator, local: modelName(answersLocal.meta.generator), hosted: answersHosted ? modelName(answersHosted.meta.generator) : dash },
    { label: t.rows.recall5, local: p(local["recall@5"]), hosted: p(hosted?.["recall@5"]) },
    { label: t.rows.mrr, local: local.mrr.toFixed(3), hosted: hosted ? hosted.mrr.toFixed(3) : dash },
    { label: t.rows.correct, local: p(answersLocal.correctness), hosted: p(answersHosted?.correctness) },
    { label: t.rows.faithful, local: p(answersLocal.faithfulness), hosted: p(answersHosted?.faithfulness) },
    { label: t.rows.validity, local: p(answersLocal.citation_validity), hosted: p(answersHosted?.citation_validity) },
    { label: t.rows.withCitation, local: p(answersLocal.answers_with_citation), hosted: p(answersHosted?.answers_with_citation) },
    { label: t.rows.abstain, local: p(answersLocal.unanswerable_abstention, 0), hosted: p(answersHosted?.unanswerable_abstention, 0) },
    { label: t.rows.falseAbstain, local: p(answersLocal.false_abstention, 1), hosted: p(answersHosted?.false_abstention, 1) },
    { label: t.rows.latency, local: s(answersLocal.p50_total_ms), hosted: s(answersHosted?.p50_total_ms) },
  ];

  const chart = (modes: Partial<Record<ModeKey, { "recall@5": number }>> | undefined, keys: ModeKey[]) =>
    keys.filter((k) => modes?.[k]).map((k) => ({ label: t.modes[k], value: modes![k]!["recall@5"] }));
  const cross = (key: "cross_ar_en" | "cross_en_ar") => ({
    keyword: p(lm.bm25!["by_type_recall@5"][key], 0),
    meaning: p(lm.dense!["by_type_recall@5"][key], 0),
  });

  return (
    <div className="mx-auto w-full max-w-[76rem] px-5 pb-24 pt-14 sm:px-8 sm:pt-20 lg:pb-32">
      <header className="max-w-3xl">
        <h1 className={`text-h1 font-semibold ${lang === "ar" ? "font-display-ar font-bold" : ""}`}>{t.title}</h1>
        <p className="mt-5 text-lead text-ink">{t.lead}</p>
      </header>

      <Section id="pipeline" title={t.pipelineTitle} lead={t.pipelineLead}>
        <Pipeline lang={lang} />
      </Section>

      <Section id="compare" title={t.compareTitle} lead={t.compareLead(modelName(answersLocal.meta.judge))}>
        <div className="overflow-x-auto">
          <table className="w-full min-w-[20rem] border-collapse text-small">
            <thead>
              <tr className="border-b-2 border-line-strong text-ink">
                <th scope="col" className="w-[44%] py-3 pe-4 text-start font-semibold">
                  {t.colMeasure}
                </th>
                <th scope="col" className="py-3 pe-4 text-start font-semibold">
                  {t.colLocal}
                </th>
                <th scope="col" className="py-3 text-start font-semibold">
                  {t.colHosted}
                </th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.label} className="border-b border-line">
                  <th scope="row" className="py-3 pe-4 text-start font-normal text-ink-muted">
                    {row.label}
                  </th>
                  <td className="tabular py-3 pe-4 text-ink">
                    <bdi>{row.local}</bdi>
                  </td>
                  <td className="tabular py-3 font-medium text-ink">
                    <bdi>{row.hosted}</bdi>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="mt-4 text-caption text-ink-muted">
          {t.compareNote(retrievalLocal.meta.n_questions, answersLocal.n_answerable, answersLocal.n_unanswerable)}
        </p>
      </Section>

      <Section id="stages" title={t.stagesTitle} lead={t.stagesLead}>
        <div className="grid gap-5 lg:grid-cols-2">
          <BarChart title={t.chartLocal} rows={chart(lm, ["bm25", "dense", "hybrid", "hybrid_rerank"])} notMeasured={dash} />
          {hm && <BarChart title={t.chartHosted} rows={chart(hm, ["bm25", "dense", "hybrid"])} notMeasured={dash} />}
        </div>
      </Section>

      <Section id="cross" title={t.crossTitle} lead={t.crossLead}>
        <dl className="grid gap-5 md:grid-cols-2">
          {[
            { label: t.crossArEn, ...cross("cross_ar_en") },
            { label: t.crossEnAr, ...cross("cross_en_ar") },
          ].map((c) => (
            <div key={c.label} className="rounded-lg bg-surface p-6 sm:p-7">
              <dt className="font-semibold text-ink">{c.label}</dt>
              <dd className="mt-5 grid grid-cols-2 gap-4">
                <div>
                  <p className="tabular text-h1 font-semibold text-ink-muted">
                    <bdi dir="ltr">{c.keyword}</bdi>
                  </p>
                  <p className="mt-1 text-small text-ink-muted">{t.crossKeyword}</p>
                </div>
                <div>
                  <p className="tabular text-h1 font-semibold text-accent">
                    <bdi dir="ltr">{c.meaning}</bdi>
                  </p>
                  <p className="mt-1 text-small text-ink-muted">{t.crossMeaning}</p>
                </div>
              </dd>
            </div>
          ))}
        </dl>
      </Section>

      <Section id="prompt" title={t.promptTitle} lead={t.promptLead}>
        <div className="grid gap-10 lg:grid-cols-12">
          <div className="lg:col-span-7">
            <BarChart
              title={t.rows.withCitation}
              rows={promptAblation.map((r, i) => ({ label: t.promptLabels[i] ?? r.label, value: r.answers_with_citation }))}
              notMeasured={dash}
            />
          </div>
          <p className="text-body text-ink lg:col-span-5">
            {t.promptBody(p(1 - judgeAgreement.agreement, 0), judgeAgreement.kappa.toFixed(2))}
          </p>
        </div>
      </Section>

      <Section id="limits" title={t.limitsTitle}>
        <ul className="max-w-3xl space-y-4">
          {t.limits(testset.n).map((item) => (
            <li key={item} className="grid grid-cols-[1.25rem_minmax(0,1fr)] text-body text-ink">
              <span className="mt-[0.7em] size-1.5 rounded-full bg-brand-gold" aria-hidden />
              <span>{item}</span>
            </li>
          ))}
        </ul>
        <a href={REPO_URL} target="_blank" rel="noreferrer" className="link mt-8 inline-flex items-center gap-1 text-body">
          {t.repo}
          <ArrowUpRight size={16} strokeWidth={1.75} className="rtl:-scale-x-100" aria-hidden />
        </a>
      </Section>
    </div>
  );
}
