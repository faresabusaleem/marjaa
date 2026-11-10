// Measured results for the pages. Every value comes from src/data/results.json,
// which scripts/update_readme.py writes from the eval runs in evals/results/.

import results from "@/data/results.json";

export type ModeKey = "bm25" | "dense" | "hybrid" | "hybrid_rerank";

interface ModeStats {
  "recall@1": number;
  "recall@5": number;
  mrr: number;
  "by_type_recall@5": Record<string, number>;
}

interface RetrievalRun {
  meta: { n_questions: number; embedder: string };
  modes: Partial<Record<ModeKey, ModeStats>>;
}

export interface AnswerRun {
  meta: { generator: string; judge: string };
  n_answerable: number;
  n_unanswerable: number;
  correctness: number;
  faithfulness: number;
  citation_validity: number;
  answers_with_citation: number;
  unanswerable_abstention: number;
  false_abstention: number;
  p50_total_ms: number;
}

export const testset = results.testset;
export const retrievalLocal = results.retrieval.local as RetrievalRun;
export const retrievalHosted = results.retrieval.hosted as RetrievalRun | null;
export const answersLocal = results.answers.local as AnswerRun;
export const answersHosted = results.answers.hosted as AnswerRun | null;
export const promptAblation = results.prompt_ablation;
export const judgeAgreement = results.judge_agreement;

/** 0.9757 -> "97.6%"; numbers stay in Western digits in both languages, as on UAE government sites. */
export const pct = (v: number | null | undefined, digits = 1) => (v == null ? null : `${(v * 100).toFixed(digits)}%`);
export const secs = (ms: number | null | undefined) => (ms == null ? null : (ms / 1000).toFixed(1));

/** "ollama:qwen3.5:4b" -> "Qwen 3.5 4B"; "gemini:gemini-3.5-flash-lite" -> "Gemini 3.5 Flash-Lite". */
export function modelName(id: string): string {
  return id
    .replace(/^(ollama|gemini):/, "")
    .replace(/^qwen([\d.]+):(\w+)$/i, (_, v: string, size: string) => `Qwen ${v} ${size.toUpperCase()}`)
    .replace(/^gemini-([\d.]+)-(.*)$/i, (_, v: string, rest: string) =>
      `Gemini ${v} ${rest.split("-").map((w) => w[0].toUpperCase() + w.slice(1)).join("-")}`,
    );
}

/** "BAAI/bge-m3" -> "BGE-M3"; "gemini-embedding-2" -> "Gemini Embedding 2". */
export function embedderName(id: string): string {
  if (/bge-m3/i.test(id)) return "BGE-M3";
  return id
    .split("-")
    .map((w) => w[0].toUpperCase() + w.slice(1))
    .join(" ");
}

/** The headline figures shown on the Ask page: the hosted pipeline this site runs. */
export function headline() {
  const r = retrievalHosted?.modes.hybrid ?? retrievalLocal.modes.hybrid_rerank!;
  const a = answersHosted ?? answersLocal;
  return {
    questions: testset.n,
    recall5: pct(r["recall@5"])!,
    citationValidity: pct(a.citation_validity)!,
    abstention: pct(a.unanswerable_abstention, 0)!,
  };
}
