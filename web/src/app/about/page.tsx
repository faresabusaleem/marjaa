import type { Metadata } from "next";
import { BarChart } from "@/components/BarChart";
import { External, GitHub } from "@/components/Icons";
import results from "@/data/results.json";
import { REPO_URL } from "@/lib/i18n";

export const metadata: Metadata = {
  title: "How Marjaa works · مرجع",
  description: "The retrieval pipeline behind Marjaa and how it was evaluated, with measured results.",
};

// Every number on this page comes from web/src/data/results.json, which
// scripts/update_readme.py writes from the eval runs in evals/results/.
type Answers = NonNullable<(typeof results)["answers"]["local"]>;
type Retrieval = NonNullable<(typeof results)["retrieval"]["local"]>;

const pct = (v: number | null | undefined, digits = 1) => (v == null ? "—" : `${(v * 100).toFixed(digits)}%`);
const secs = (ms: number | null | undefined) => (ms == null ? "—" : `${(ms / 1000).toFixed(1)} s`);
// "ollama:qwen3.5:4b" -> "Qwen 3.5 4B", "gemini:gemini-3.5-flash-lite" -> "Gemini 3.5 Flash-Lite"
const modelName = (id: string) =>
  id
    .replace(/^(ollama|gemini):/, "")
    .replace(/^qwen([\d.]+):(\w+)$/i, (_, v: string, size: string) => `Qwen ${v} ${size.toUpperCase()}`)
    .replace(/^gemini-([\d.]+)-(.*)$/i, (_, v: string, rest: string) =>
      `Gemini ${v} ${rest.split("-").map((w) => w[0].toUpperCase() + w.slice(1)).join("-")}`,
    );

const STEPS = [
  {
    title: "Parse and chunk",
    body: "The official Arabic and English PDFs are parsed with the cleanest of three parsers (scored on Arabic text quality) and split into one chunk per article: 159 chunks.",
  },
  {
    title: "Hybrid search",
    body: "Keyword search (BM25 over normalised, light-stemmed Arabic and English) and vector search run side by side; Reciprocal Rank Fusion merges the two rankings.",
  },
  {
    title: "Rerank",
    body: "A cross-encoder (BGE reranker v2-m3) reads each question–article pair and puts the right article first.",
    tag: "Local only",
  },
  {
    title: "Confidence gate",
    body: "If the best match scores below a threshold calibrated on held-out questions, the answer is “not found” and the LLM is never called.",
  },
  {
    title: "Cited answer",
    body: "The LLM sees the top five articles and must end every sentence with its citation, in the question's language.",
  },
  {
    title: "Citation check",
    body: "Every citation is parsed in code and accepted only if that article was actually retrieved; the interface shows the result on each chip.",
  },
];

export default function About() {
  const local = results.retrieval.local as Retrieval;
  const hosted = results.retrieval.hosted as Retrieval | null;
  const ansLocal = results.answers.local as Answers;
  const ansHosted = results.answers.hosted as Answers | null;
  const lm = local.modes;
  const hostedMode = hosted?.modes?.hybrid ?? null;

  const comparison: { label: string; local: string; hosted: string }[] = [
    { label: "Embeddings", local: "BGE-M3 (local)", hosted: "Gemini embedding 2 (API)" },
    { label: "Reranker", local: "BGE reranker v2-m3", hosted: "None (bundle-size limit)" },
    { label: "Answer model", local: modelName(ansLocal.meta.generator), hosted: ansHosted ? modelName(ansHosted.meta.generator) : "Gemini 3.5 Flash-Lite" },
    { label: "Right article in top 5", local: pct(lm.hybrid_rerank["recall@5"]), hosted: pct(hostedMode?.["recall@5"]) },
    { label: "Right article ranked first (MRR)", local: lm.hybrid_rerank.mrr.toFixed(3), hosted: hostedMode ? hostedMode.mrr.toFixed(3) : "—" },
    { label: "Correct answers (LLM judge)", local: pct(ansLocal.correctness), hosted: pct(ansHosted?.correctness) },
    { label: "Faithful to the articles (LLM judge)", local: pct(ansLocal.faithfulness), hosted: pct(ansHosted?.faithfulness) },
    { label: "Citations pointing to a retrieved article", local: pct(ansLocal.citation_validity), hosted: pct(ansHosted?.citation_validity) },
    { label: "Out-of-scope questions answered “not found”", local: pct(ansLocal.unanswerable_abstention, 0), hosted: pct(ansHosted?.unanswerable_abstention, 0) },
    { label: "In-scope questions wrongly “not found”", local: pct(ansLocal.false_abstention, 0), hosted: pct(ansHosted?.false_abstention, 0) },
    { label: "Median time to full answer", local: secs(ansLocal.p50_total_ms), hosted: secs(ansHosted?.p50_total_ms) },
  ];

  const crossBm25 = lm.bm25["by_type_recall@5"];
  const crossDense = lm.dense["by_type_recall@5"];
  const agreement = results.judge_agreement;

  return (
    <main dir="ltr" lang="en" className="mx-auto max-w-4xl px-4 pb-24 pt-12 sm:px-6 sm:pt-16">
      <p className="text-xs font-medium uppercase tracking-wider text-accent">How it works</p>
      <h1 className="font-read mt-3 text-[2.2rem] font-semibold leading-tight tracking-tight sm:text-[2.8rem]">
        Retrieval you can check, answers you can trace
      </h1>
      <p className="mt-4 max-w-2xl text-[1.05rem] leading-7 text-muted">
        Marjaa is a retrieval-augmented generation (RAG) system over the UAE Federal Labour Law. It was built
        to be measured: {results.testset.n} test questions in Arabic and English, every number below from an
        actual run, and the code that produced them on GitHub.
      </p>
      <div className="mt-6 flex flex-wrap gap-3">
        <a href={REPO_URL} target="_blank" rel="noreferrer" className="inline-flex items-center gap-2 rounded-xl bg-ink px-4 py-2.5 text-sm font-medium text-bg hover:opacity-90">
          <GitHub /> Code and full results
        </a>
        <a href="/" className="inline-flex items-center gap-2 rounded-xl border border-line bg-surface px-4 py-2.5 text-sm font-medium hover:border-accent-line">
          Try it
        </a>
      </div>

      <section className="mt-16">
        <h2 className="text-xl font-semibold">The pipeline</h2>
        <ol className="mt-5 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {STEPS.map((s, i) => (
            <li key={s.title} className="relative rounded-2xl border border-line bg-surface p-5">
              <div className="flex items-center gap-2.5">
                <span className="grid size-7 place-items-center rounded-full bg-accent-soft text-sm font-semibold text-accent tabular-nums">
                  {i + 1}
                </span>
                <span className="font-medium">{s.title}</span>
                {s.tag && <span className="ms-auto rounded-full border border-line px-2 py-0.5 text-[11px] text-muted">{s.tag}</span>}
              </div>
              <p className="mt-2.5 text-sm leading-6 text-muted">{s.body}</p>
            </li>
          ))}
        </ol>
      </section>

      <section className="mt-16">
        <h2 className="text-xl font-semibold">Two deployments, one evaluation</h2>
        <p className="mt-2 max-w-2xl text-muted">
          The full pipeline needs about 4.5 GB of models and a GPU, which a free serverless host cannot run. This
          site uses a lighter version: Gemini embeddings and answers, no reranker. Both were measured with the
          same test questions and the same judge ({modelName(ansLocal.meta.judge)}).
        </p>
        <div className="mt-5 overflow-x-auto rounded-2xl border border-line bg-surface">
          <table className="w-full min-w-[34rem] text-sm">
            <thead>
              <tr className="border-b border-line text-start text-muted">
                <th className="px-5 py-3 text-start font-medium" scope="col" />
                <th className="px-5 py-3 text-start font-medium" scope="col">Local (open models)</th>
                <th className="px-5 py-3 text-start font-medium" scope="col">This site (hosted)</th>
              </tr>
            </thead>
            <tbody>
              {comparison.map((row) => (
                <tr key={row.label} className="border-b border-line last:border-0">
                  <th scope="row" className="px-5 py-2.5 text-start font-normal text-muted">{row.label}</th>
                  <td className="px-5 py-2.5 tabular-nums">{row.local}</td>
                  <td className="px-5 py-2.5 tabular-nums">{row.hosted}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="mt-2 text-xs text-faint">
          Retrieval: {local.meta.n_questions} answerable questions. Answers: the test split ({ansLocal.n_answerable} answerable +{" "}
          {ansLocal.n_unanswerable} out of scope). “—” means not measured.
        </p>
      </section>

      <section className="mt-16 grid gap-5">
        <h2 className="text-xl font-semibold">What each stage adds</h2>
        <BarChart
          title="Right article in the top 5 (Recall@5), local pipeline"
          caption={`${local.meta.n_questions} answerable questions, one chunk per article.`}
          rows={[
            { label: "BM25 (keywords)", value: lm.bm25["recall@5"] },
            { label: "Dense (BGE-M3)", value: lm.dense["recall@5"] },
            { label: "Hybrid (RRF)", value: lm.hybrid["recall@5"] },
            { label: "Hybrid + rerank", value: lm.hybrid_rerank["recall@5"] },
          ]}
        />
        <div className="grid gap-3 sm:grid-cols-2">
          {[
            { label: "Arabic question → English article", key: "cross_ar_en" as const },
            { label: "English question → Arabic article", key: "cross_en_ar" as const },
          ].map((c) => (
            <div key={c.key} className="rounded-2xl border border-line bg-surface p-5">
              <p className="text-sm text-muted">{c.label}</p>
              <div className="mt-3 flex items-baseline gap-6">
                <div>
                  <p className="text-2xl font-semibold tabular-nums">{pct(crossBm25[c.key], 0)}</p>
                  <p className="text-xs text-muted">keyword search</p>
                </div>
                <div>
                  <p className="text-2xl font-semibold tabular-nums">{pct(crossDense[c.key], 0)}</p>
                  <p className="text-xs text-muted">vector search</p>
                </div>
              </div>
            </div>
          ))}
        </div>
        <p className="text-sm leading-6 text-muted">
          Keyword search cannot cross languages; multilingual embeddings can, and fusion keeps those hits while
          BM25 stays perfect on same-language questions.
        </p>
      </section>

      <section className="mt-16 grid gap-5">
        <h2 className="text-xl font-semibold">One example fixed the citations</h2>
        <BarChart
          title="Answers carrying at least one citation"
          caption="Same questions and retrieval; only the prompt changed."
          rows={results.prompt_ablation.map((r) => ({ label: r.label, value: r.answers_with_citation }))}
        />
        <p className="text-sm leading-6 text-muted">
          With rules alone the 4B model skipped citations in about one answer in five. A two-sentence format
          example fixed it. The example is deliberately about park opening hours: an earlier one about study
          leave was copied word for word into a real answer.
          {agreement &&
            ` Judged correctness barely moved, and the two judges disagree on ${pct(1 - agreement.agreement, 0)} of identical answers (Cohen's kappa ${agreement.kappa.toFixed(2)}), so the prompt is credited only with the citation gains, which are checked in code.`}
        </p>
      </section>

      <section className="mt-16">
        <h2 className="text-xl font-semibold">Limits worth knowing</h2>
        <ul className="mt-4 space-y-2.5 text-[0.95rem] leading-7 text-muted">
          <li>
            The {results.testset.n} questions were generated by an LLM from the law text and are not
            human-verified; they reuse the law&apos;s wording, so treat retrieval scores as an upper bound.
          </li>
          <li>Correctness and faithfulness are graded by an LLM judge, not by lawyers.</li>
          <li>Only the Labour Law is indexed. Later amendments appear only if they are in the official PDFs.</li>
          <li>Not legal advice. The Arabic text is the legally authoritative version.</li>
        </ul>
        <a href={REPO_URL} target="_blank" rel="noreferrer" className="mt-6 inline-flex items-center gap-1.5 text-sm text-accent hover:underline">
          Methods, ablations and every result table in the README <External size={14} />
        </a>
      </section>
    </main>
  );
}
