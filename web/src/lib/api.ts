// Types and a streaming client for the Marjaa API (src/marjaa/api/app.py).

export type Lang = "en" | "ar";

export interface Source {
  id: string;
  citation: string;
  law_name: string;
  article: number | null;
  language: Lang;
  page_start: number;
  page_end: number;
  score: number;
  text: string;
}

export interface Citation {
  text: string;
  law_id: string | null;
  article: number;
  valid: boolean;
  chunk_id: string | null;
}

export interface Done {
  trace_id: string;
  question: string;
  search_query: string | null;
  language: Lang;
  answer: string;
  abstained: boolean;
  abstain_reason: "low_relevance" | "model" | null;
  top_relevance: number | null;
  citations: Citation[];
  citation_coverage: number;
  latency_ms: Record<string, number>;
  provider: string;
  model: string;
}

export interface Chunk {
  id: string;
  law_name: string;
  law_name_en: string;
  law_name_ar: string;
  law_number: number;
  law_year: number;
  language: Lang;
  article: number | null;
  part: number;
  title: string;
  text: string;
  page_start: number;
  page_end: number;
}

export interface HistoryTurn {
  question: string;
  answer: string;
}

export type StreamEvent =
  | { event: "sources"; data: { trace_id: string; language: Lang; search_query: string | null; sources: Source[] } }
  | { event: "token"; data: { text: string } }
  | { event: "done"; data: Done }
  | { event: "error"; data: { code: "busy" | "error"; message: string } };

export class ApiError extends Error {
  constructor(
    message: string,
    readonly code: "busy" | "unavailable" | "error",
  ) {
    super(message);
  }
}

/** POST /api/ask and yield its Server-Sent Events as they arrive. */
export async function* ask(
  question: string,
  history: HistoryTurn[],
  signal?: AbortSignal,
): AsyncGenerator<StreamEvent> {
  const res = await fetch("/api/ask", {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
    body: JSON.stringify({ question, history }),
    signal,
  });
  if (!res.ok || !res.body) {
    const code = res.status === 429 ? "busy" : res.status === 503 ? "unavailable" : "error";
    throw new ApiError(`HTTP ${res.status}`, code);
  }
  const reader = res.body.pipeThrough(new TextDecoderStream()).getReader();
  let buffer = "";
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += value;
    let end: number;
    while ((end = buffer.indexOf("\n\n")) !== -1) {
      const block = buffer.slice(0, end);
      buffer = buffer.slice(end + 2);
      const event = parseBlock(block);
      if (event) yield event;
    }
  }
}

function parseBlock(block: string): StreamEvent | null {
  let event = "";
  const data: string[] = [];
  for (const line of block.split("\n")) {
    if (line.startsWith("event:")) event = line.slice(6).trim();
    else if (line.startsWith("data:")) data.push(line.slice(5).replace(/^ /, ""));
  }
  if (!event || !data.length) return null;
  return { event, data: JSON.parse(data.join("\n")) } as StreamEvent;
}

const chunkCache = new Map<string, Promise<Chunk | null>>();

/** GET /api/sources/{id}; null if it does not exist (e.g. no English copy). */
export function getChunk(id: string): Promise<Chunk | null> {
  let hit = chunkCache.get(id);
  if (!hit) {
    hit = fetch(`/api/sources/${encodeURIComponent(id)}`)
      .then((r) => (r.ok ? (r.json() as Promise<Chunk>) : null))
      .catch(() => null);
    chunkCache.set(id, hit);
  }
  return hit;
}

/** The same article in the other language: …-ar-a029-p0 <-> …-en-a029-p0 */
export function counterpartId(id: string): string {
  return id.includes("-ar-") ? id.replace("-ar-", "-en-") : id.replace("-en-", "-ar-");
}
