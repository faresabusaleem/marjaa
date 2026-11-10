import { describe, expect, it } from "vitest";
import law from "@/data/law.json";
import { splitCitations, toAsciiDigits } from "./citations";
import { formatLawText } from "./lawText";
import { langOfPath, localePath, stripLocale } from "./locale";
import { excerpt, normalize, search, terms, type IndexEntry } from "./search";

describe("formatLawText", () => {
  it("rejoins PDF lines into numbered clauses and lettered items", () => {
    const blocks = formatLawText(
      "1. Without prejudice to the Worker's rights acquired for the\nperiod preceding:\na. Thirty days for each year.\nb. Two days for each month if his\nservice is more than six months.",
    );
    expect(blocks).toEqual([
      { marker: "1.", text: "Without prejudice to the Worker's rights acquired for the period preceding:" },
      { marker: "a.", text: "Thirty days for each year." },
      { marker: "b.", text: "Two days for each month if his service is more than six months." },
    ]);
  });

  it("handles Arabic clauses and definition lines", () => {
    const blocks = formatLawText("الدولة : الإمارات العربية المتحدة.\nالوزارة : وزارة الموارد البشرية\nوالتوطين.\nأ. ثلاثين يومًا.");
    expect(blocks).toEqual([
      { term: "الدولة", text: "الإمارات العربية المتحدة." },
      { term: "الوزارة", text: "وزارة الموارد البشرية والتوطين." },
      { marker: "أ.", text: "ثلاثين يومًا." },
    ]);
  });

  it("joins a definition whose colon starts the next line", () => {
    expect(formatLawText("Establishment\n: Every economic unit\nin the State.")).toEqual([
      { term: "Establishment", text: "Every economic unit in the State." },
    ]);
  });

  it("keeps a sentence together across a page break", () => {
    expect(formatLawText("The Worker is entitled to\n\n\nfull pay.")).toEqual([{ text: "The Worker is entitled to full pay." }]);
  });

  it("loses no words from any article", () => {
    for (const a of law.articles) {
      for (const v of [a.ar, a.en]) {
        const words = (s: string) => s.replace(/\s+/g, "");
        const blocks = formatLawText(v.text);
        const rebuilt = blocks.map((b) => `${b.marker ?? ""}${b.term ?? ""}${b.text}`).join("");
        expect(words(rebuilt).replace(/:/g, "")).toBe(words(v.text).replace(/:/g, ""));
      }
    }
  });
});

describe("search", () => {
  const index: IndexEntry[] = [
    { n: 29, titles: { ar: "الإجازة السنوية", en: "Annual leave" }, titleWords: normalize("الإجازة السنوية Annual leave"), words: normalize("يستحق العامل إجازة سنوية Thirty days") },
    { n: 30, titles: { ar: "إجازة الوضع", en: "Maternity Leave" }, titleWords: normalize("إجازة الوضع Maternity Leave"), words: normalize("تستحق العاملة إجازة وضع") },
  ];

  it("normalises Arabic letter forms, diacritics and digits", () => {
    expect(normalize("الإجَازةُ ٢٩")).toBe("الاجازه 29");
    expect(terms("الإجازة")).toEqual(["اجازه"]);
  });

  it("finds articles in either language and ranks title matches first", () => {
    expect(search(index, "leave").map((h) => h.n)).toEqual([29, 30]);
    expect(search(index, "إجازة الوضع").map((h) => h.n)).toEqual([30]);
    expect(search(index, "thirty").map((h) => h.n)).toEqual([29]);
    expect(search(index, "nothing here")).toEqual([]);
  });

  it("treats a bare number as an article number", () => {
    expect(search(index, "30")[0].n).toBe(30);
    expect(search(index, "٢٩")[0].n).toBe(29);
  });

  it("cuts an excerpt around the first match", () => {
    expect(excerpt("The Worker shall be entitled to an annual leave with full pay", "annual")).toEqual({
      before: "The Worker shall be entitled to an",
      match: "annual",
      after: "leave with full pay",
    });
  });
});

describe("locale paths", () => {
  it("puts Arabic under /ar and English at the root", () => {
    expect(localePath("ar", "/")).toBe("/ar");
    expect(localePath("ar", "/library/29")).toBe("/ar/library/29");
    expect(localePath("en", "/ar/library/29")).toBe("/library/29");
    expect(localePath("en", "/en")).toBe("/");
    expect(stripLocale("/arabic")).toBe("/arabic");
    expect(langOfPath("/ar/about")).toBe("ar");
    expect(langOfPath("/about")).toBe("en");
  });
});

describe("citations", () => {
  it("finds citations in both languages, with Arabic-Indic digits", () => {
    const pieces = splitCitations("Thirty days [Federal Labour Law, Article 29]. ثلاثون يومًا [قانون العمل الاتحادي، المادة ٢٩].");
    const cites = pieces.filter((p) => p.kind === "cite");
    expect(cites.map((c) => (c.kind === "cite" ? c.articles : []))).toEqual([[29], [29]]);
    expect(toAsciiDigits("٤٢")).toBe("42");
  });

  it("reads several articles in one citation", () => {
    const [cite] = splitCitations("[Federal Labour Law, Articles 51 and 52]").filter((p) => p.kind === "cite");
    expect(cite.kind === "cite" && cite.articles).toEqual([51, 52]);
  });
});
