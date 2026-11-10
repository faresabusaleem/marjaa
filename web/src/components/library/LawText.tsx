import { formatLawText } from "@/lib/lawText";
import type { Lang } from "@/lib/locale";

/** Article text from the official PDFs, laid out as clauses, items and definitions. */
export function LawText({ text, lang, className }: { text: string; lang: Lang; className?: string }) {
  const blocks = formatLawText(text);
  return (
    <div lang={lang} dir={lang === "ar" ? "rtl" : "ltr"} className={`reading space-y-3 ${className ?? ""}`}>
      {blocks.map((b, i) =>
        b.marker ? (
          <div key={i} className="grid grid-cols-[2rem_minmax(0,1fr)] gap-x-1">
            <span className="tabular text-ink-muted">{b.marker}</span>
            <p>{b.text}</p>
          </div>
        ) : b.term ? (
          <p key={i}>
            <span className="font-semibold">{b.term}</span>
            <span className="text-ink-muted">{lang === "ar" ? ": " : ": "}</span>
            {b.text}
          </p>
        ) : (
          <p key={i}>{b.text}</p>
        ),
      )}
    </div>
  );
}
