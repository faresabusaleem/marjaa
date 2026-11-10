import type { Metadata } from "next";
import { LibraryBrowser } from "@/components/library/LibraryBrowser";
import { STRINGS } from "@/lib/i18n";
import { ARTICLES } from "@/lib/law";
import { isLang } from "@/lib/locale";
import { pageMetadata } from "@/lib/metadata";

export async function generateMetadata({ params }: PageProps<"/[lang]/library">): Promise<Metadata> {
  const { lang: l } = await params;
  const lang = isLang(l) ? l : "en";
  const t = STRINGS[lang];
  return pageMetadata(lang, "/library", t.library.title, t.library.lead(ARTICLES.length));
}

export default async function LibraryPage({ params }: PageProps<"/[lang]/library">) {
  const { lang: l } = await params;
  const lang = isLang(l) ? l : "en";
  const t = STRINGS[lang];
  const rows = ARTICLES.map((a) => ({ n: a.n, ar: a.ar.title, en: a.en.title }));
  return (
    <div className="mx-auto w-full max-w-[76rem] px-5 pb-24 pt-14 sm:px-8 sm:pt-20 lg:pb-32">
      <header className="max-w-3xl">
        <h1 className={`text-h1 font-semibold ${lang === "ar" ? "font-display-ar font-bold" : ""}`}>{t.library.title}</h1>
        <p className="mt-5 text-lead text-ink">{t.library.lead(ARTICLES.length)}</p>
      </header>
      <div className="mt-12">
        <LibraryBrowser rows={rows} />
      </div>
    </div>
  );
}
