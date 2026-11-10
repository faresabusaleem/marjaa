import { ArrowUpRight } from "lucide-react";
import type { Metadata } from "next";
import { PrimaryLogo } from "@/components/brand/Logo";
import { GithubMark } from "@/components/site/GithubMark";
import { AUTHOR_URL, officialUrl, STRINGS } from "@/lib/i18n";
import { isLang } from "@/lib/locale";
import { pageMetadata } from "@/lib/metadata";

export async function generateMetadata({ params }: PageProps<"/[lang]/about">): Promise<Metadata> {
  const { lang: l } = await params;
  const lang = isLang(l) ? l : "en";
  return pageMetadata(lang, "/about", STRINGS[lang].about.title, STRINGS[lang].about.lead);
}

export default async function About({ params }: PageProps<"/[lang]/about">) {
  const { lang: l } = await params;
  const lang = isLang(l) ? l : "en";
  const t = STRINGS[lang].about;

  const sections = [
    { id: "covers", title: t.whatTitle, body: t.whatBody },
    {
      id: "who",
      title: t.whoTitle,
      body: t.whoBody,
      link: (
        <a href={AUTHOR_URL} target="_blank" rel="noreferrer" className="link inline-flex items-center gap-2">
          <GithubMark size={16} />
          {t.whoLink}
        </a>
      ),
    },
    { id: "privacy", title: t.privacyTitle, body: t.privacyBody },
    {
      id: "advice",
      title: t.adviceTitle,
      body: t.adviceBody,
      link: (
        <a href={officialUrl(lang)} target="_blank" rel="noreferrer" className="link inline-flex items-center gap-1">
          {t.sourceLink}
          <ArrowUpRight size={16} strokeWidth={1.75} className="rtl:-scale-x-100" aria-hidden />
        </a>
      ),
    },
  ];

  return (
    <div className="mx-auto w-full max-w-[76rem] px-5 pb-24 pt-14 sm:px-8 sm:pt-20 lg:pb-32">
      <header className="grid gap-12 lg:grid-cols-12 lg:items-center">
        <div className="lg:col-span-8">
          <h1 className={`text-h1 font-semibold ${lang === "ar" ? "font-display-ar font-bold" : ""}`}>{t.title}</h1>
          <p className="mt-6 text-lead text-ink">{t.lead}</p>
        </div>
        <div className="lg:col-span-3 lg:col-start-10">
          <div className="grid place-items-center rounded-lg bg-surface px-8 py-10">
            <PrimaryLogo className="h-auto w-full max-w-52" title={STRINGS[lang].meta.siteName} />
          </div>
        </div>
      </header>

      <div className="mt-20 border-t border-line lg:mt-28">
        {sections.map((s) => (
          <section key={s.id} aria-labelledby={s.id} className="grid gap-4 border-b border-line py-10 lg:grid-cols-12 lg:gap-10 lg:py-12">
            <h2 id={s.id} className="text-h3 font-semibold text-ink lg:col-span-4">
              {s.title}
            </h2>
            <div className="lg:col-span-7">
              <p className="text-body text-ink">{s.body}</p>
              {s.link && <p className="mt-4 text-body">{s.link}</p>}
            </div>
          </section>
        ))}
      </div>
    </div>
  );
}
