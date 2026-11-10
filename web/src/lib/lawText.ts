// Lays out article text taken from the official PDFs. The extracted text has a
// hard line break at the end of every printed line; this rejoins those lines
// into paragraphs and keeps the breaks that mean something: numbered clauses,
// lettered items, dashes, and "Term : definition" lines.

export interface LawBlock {
  /** "1.", "a.", "أ.", "−": shown as a hanging marker. */
  marker?: string;
  /** The defined term of a "Term : definition" line (Article 1). */
  term?: string;
  text: string;
}

const MARKER = /^\s*((?:\d{1,2}|[a-zA-Z]|[\u0621-\u064A])[.)]|\(\s*(?:\d{1,2}|[a-zA-Z]|[\u0621-\u064A])\s*\)|[−–•-])\s+(.*)$/;
// "Ministry : Ministry of ..." with a short term before a spaced colon.
const DEFINITION = /^\s*([^:.،]{1,48}?)\s+:\s+(.+)$/;
const SENTENCE_END = /[.:;؛!?؟)]\s*$/;

/** Split raw article text into display blocks. */
export function formatLawText(raw: string): LawBlock[] {
  const blocks: LawBlock[] = [];
  const push = (block: LawBlock) => blocks.push(block);
  let blankBefore = false;

  for (const line of joinSplitTerms(raw.replace(/\r/g, "").split("\n").map((l) => l.trim()))) {
    if (!line) {
      blankBefore = true;
      continue;
    }
    const prev: LawBlock | undefined = blocks.at(-1);
    const marker = line.match(MARKER);
    const definition = !marker && line.match(DEFINITION);

    if (marker) {
      push({ marker: marker[1].replace(/\s+/g, ""), text: marker[2] });
    } else if (definition && (!prev || SENTENCE_END.test(prev.text) || prev.term !== undefined)) {
      push({ term: definition[1], text: definition[2] });
    } else if (!prev || (blankBefore && SENTENCE_END.test(prev.text)) || /:\s*$/.test(prev.text)) {
      push({ text: line });
    } else {
      prev.text = `${prev.text} ${line}`;
    }
    blankBefore = false;
  }
  return blocks;
}

/**
 * The PDF sometimes sets a defined term on its own line(s) and starts the next
 * line with the colon: "Employment\nContract\n: Every agreement...". Join those
 * into one "Employment Contract : Every agreement..." line.
 */
function joinSplitTerms(lines: string[]): string[] {
  const out: string[] = [];
  const isTermLine = (l: string | undefined) => !!l && l.length <= 32 && !l.includes(":") && !SENTENCE_END.test(l);
  for (const line of lines) {
    const last = out.at(-1);
    // "Work Injury :" at the end of a line, its definition on the next one.
    if (line && last && /^[^:.]{1,32}\s:$/.test(last)) {
      out[out.length - 1] = `${last} ${line}`;
      continue;
    }
    if (!line.startsWith(":")) {
      out.push(line);
      continue;
    }
    let start = out.length;
    while (start > 0 && out.length - start < 3 && isTermLine(out[start - 1])) start--;
    const before = out[start - 1];
    if (start < out.length && (start === 0 || !before || SENTENCE_END.test(before))) {
      const term = out.splice(start).join(" ");
      out.push(`${term} ${line}`);
    } else {
      out.push(line.replace(/^:\s*/, ""));
    }
  }
  return out;
}
