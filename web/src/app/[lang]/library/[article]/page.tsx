import { ArrowLeft, ArrowRight, ArrowUpRight, MessageSquareText } from "lucide-react";
import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { LawText } from "@/components/library/LawText";
import { officialUrl, STRINGS } from "@/lib/i18n";
import { ARTICLES, getArticle, PREAMBLE, type Version } from "@/lib/law";
import { type Lang, isLang, LANGS, localePath } from "@/lib/locale";
import { pageMetadata } from "@/lib/metadata";

export const dynamicParams = false;
export function generateStaticParams() {
  return LANGS.flatMap((lang) => [...ARTICLES.map((a) => ({ lang, article: String(a.n) })), { lang, article: "preamble" }]);
}

function resolve(article: string) {
  if (article === "preamble") return { n: null, ar: PREAMBLE.ar, en: PREAMBLE.en };
  const a = /^\d+$/.test(article) ? getArticle(Number(article)) : undefined;
  return a ? { n: a.n, ar: a.ar, en: a.en } : null;
}

function heading(lang: Lang, n: number | null, v: { ar: Version; en: Version }) {
  const t = STRINGS[lang].library;
  if (n === null) return t.preamble;
  return t.articleTitle(n, v[lang].title || v[lang === "ar" ? "en" : "ar"].title);
}

export async function generateMetadata({ params }: PageProps<"/[lang]/library/[article]">): Promise<Metadata> {
  const { lang: l, article } = await params;
  const lang = isLang(l) ? l : "en";
  const a = resolve(article);
  if (!a) return {};
  const text = a[lang].text.replace(/\s+/g, " ").trim();
  return pageMetadata(lang, `/library/${article}`, heading(lang, a.n, a), text.length > 180 ? `${text.slice(0, 177)}…` : text);
}

export default async function ArticlePage({ params }: PageProps<"/[lang]/library/[article]">) {
  const { lang: l, article } = await params;
  if (!isLang(l)) notFound();
  const lang = l;
  const a = resolve(article);
  if (!a) notFound();
  const t = STRINGS[lang];
  const other: Lang = lang === "ar" ? "en" : "ar";
  const prev = a.n === null ? null : a.n === 1 ? "preamble" : String(a.n - 1);
  const next = a.n === null ? "1" : a.n < ARTICLES.length ? String(a.n + 1) : null;
  const label = (key: string | null) =>
    key === "preamble" ? t.library.preamble : key ? heading(lang, Number(key), getArticle(Number(key))!) : "";
  const title = a.n === null ? "" : a[lang].title || a[other].title;
  const pages = (v: Version) => t.library.pages(v.pages[0], v.pages[1]);

  // Physical layout on wide screens: English on the left, Arabic on the right,
  // as in the bilingual official gazette. On phones the interface language comes first.
  const column = (v: Version, l: Lang) => (
    <section
      lang={l}
      dir={l === "ar" ? "rtl" : "ltr"}
      aria-labelledby={`col-${l}`}
      className={`min-w-0 ${l === lang ? "order-first lg:order-none" : ""}`}
    >
      <div className="flex items-baseline justify-between gap-4 border-b border-line-strong pb-3">
        <h2 id={`col-${l}`} className="text-small font-semibold text-ink">
          {STRINGS[l].library[l === "ar" ? "arabicColumn" : "englishColumn"]}
          <span className="font-normal text-ink-muted"> · {STRINGS[l].library[l === "ar" ? "authoritative" : "translation"]}</span>
        </h2>
        <span className="text-caption text-ink-muted">{STRINGS[l].library.pages(v.pages[0], v.pages[1])}</span>
      </div>
      {v.title && <p className="mt-6 text-h3 font-semibold text-ink">{v.title}</p>}
      <LawText text={v.text} lang={l} className="mt-4 text-ink" />
    </section>
  );

  return (
    <article className="mx-auto w-full max-w-[76rem] px-5 pb-24 pt-10 sm:px-8 sm:pt-14 lg:pb-32">
      <nav aria-label={t.nav.library} className="text-small">
        <Link href={localePath(lang, "/library")} className="link">
          {t.library.backToIndex}
        </Link>
      </nav>

      <header className="mt-8 grid gap-6 lg:grid-cols-12 lg:items-end">
        <div className="lg:col-span-8">
          <p className="text-small text-ink-muted">{lang === "ar" ? "المرسوم بقانون اتحادي رقم 33 لسنة 2021" : "Federal Decree-Law No. 33 of 2021"}</p>
          <h1 className="mt-2 text-h1 font-semibold text-ink">
            {a.n === null ? t.library.preamble : t.panel.article(a.n)}
            {title && <span className="block text-h2 font-normal text-ink-muted">{title}</span>}
          </h1>
        </div>
        <div className="flex flex-wrap gap-3 lg:col-span-4 lg:justify-end">
          {a.n !== null && (
            <Link
              href={`${localePath(lang, "/")}?q=${encodeURIComponent(t.library.askQuestion(a.n, a[lang].title))}`}
              className="inline-flex h-11 items-center gap-2 rounded-md bg-accent-fill px-4 text-small font-medium text-on-accent transition-colors hover:bg-accent-fill-hover active:bg-accent-fill-press"
            >
              <MessageSquareText size={17} strokeWidth={1.75} aria-hidden />
              {t.library.ask}
            </Link>
          )}
          <a
            href={officialUrl(lang)}
            target="_blank"
            rel="noreferrer"
            className="inline-flex h-11 items-center gap-1.5 rounded-md border border-line-strong px-4 text-small font-medium text-ink transition-colors hover:bg-surface"
          >
            {t.panel.official}
            <ArrowUpRight size={16} strokeWidth={1.75} className="rtl:-scale-x-100" aria-hidden />
          </a>
        </div>
      </header>

      <div dir="ltr" className="mt-12 grid gap-x-16 gap-y-14 lg:grid-cols-2">
        {column(a.en, "en")}
        {column(a.ar, "ar")}
      </div>
      <p className="sr-only">{pages(a[lang])}</p>

      <nav aria-label={t.library.backToIndex} className="mt-20 grid gap-4 border-t border-line pt-8 sm:grid-cols-2">
        {prev ? (
          <Link href={localePath(lang, `/library/${prev}`)} className="group rounded-lg p-4 transition-colors hover:bg-surface sm:-ms-4">
            <span className="inline-flex items-center gap-1.5 text-small text-ink-muted">
              <ArrowLeft size={16} strokeWidth={1.75} className="rtl:-scale-x-100" aria-hidden />
              {t.library.previous}
            </span>
            <span className="mt-1 block font-medium text-ink group-hover:text-accent">{label(prev)}</span>
          </Link>
        ) : (
          <span />
        )}
        {next && (
          <Link href={localePath(lang, `/library/${next}`)} className="group rounded-lg p-4 text-end transition-colors hover:bg-surface sm:-me-4">
            <span className="inline-flex items-center gap-1.5 text-small text-ink-muted">
              {t.library.next}
              <ArrowRight size={16} strokeWidth={1.75} className="rtl:-scale-x-100" aria-hidden />
            </span>
            <span className="mt-1 block font-medium text-ink group-hover:text-accent">{label(next)}</span>
          </Link>
        )}
      </nav>
    </article>
  );
}
