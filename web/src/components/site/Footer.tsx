import { ArrowUpRight } from "lucide-react";
import Link from "next/link";
import { AUTHOR_URL, officialUrl, REPO_URL, STRINGS } from "@/lib/i18n";
import { type Lang, localePath } from "@/lib/locale";
import { PrimaryLogo, SaduBand } from "../brand/Logo";

export function Footer({ lang }: { lang: Lang }) {
  const t = STRINGS[lang];
  const nav = [
    { href: "/", label: t.nav.ask },
    { href: "/library", label: t.nav.library },
    { href: "/how-it-works", label: t.nav.how },
    { href: "/about", label: t.nav.about },
  ];
  return (
    <footer className="mt-auto">
      <SaduBand tile={22} className="block" />
      <div className="bg-surface">
        <div className="mx-auto grid max-w-[76rem] gap-10 px-5 pb-10 pt-12 sm:px-8 md:grid-cols-12">
          <div className="md:col-span-5">
            <PrimaryLogo className="h-auto w-36" title={t.meta.siteName} />
            <p className="mt-5 max-w-xs text-small text-ink-muted">{t.footer.tagline}</p>
          </div>
          <nav aria-label={t.nav.main} className="md:col-span-3">
            <ul className="space-y-2.5 text-small">
              {nav.map((n) => (
                <li key={n.href}>
                  <Link href={localePath(lang, n.href)} className="text-ink hover:text-accent">
                    {n.label}
                  </Link>
                </li>
              ))}
            </ul>
          </nav>
          <div className="space-y-5 text-small md:col-span-4">
            <div>
              <p className="text-ink-muted">{t.footer.source}</p>
              <a href={officialUrl(lang)} target="_blank" rel="noreferrer" className="mt-1 block text-ink hover:text-accent">
                {t.footer.sourceName}
                <ArrowUpRight size={15} strokeWidth={1.75} className="ms-1 inline-block align-[-0.15em] rtl:-scale-x-100" aria-hidden />
              </a>
            </div>
            <div className="flex flex-col gap-1">
              <a href={REPO_URL} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 text-ink hover:text-accent">
                {t.footer.code}
                <ArrowUpRight size={15} strokeWidth={1.75} className="rtl:-scale-x-100" aria-hidden />
              </a>
              <a href={AUTHOR_URL} target="_blank" rel="noreferrer" className="text-ink-muted hover:text-ink">
                {t.footer.builtBy}
              </a>
            </div>
          </div>
        </div>
        <div className="mx-auto max-w-[76rem] px-5 sm:px-8">
          <p className="border-t border-line py-6 text-caption text-ink-muted">{t.footer.notAdvice}</p>
        </div>
      </div>
    </footer>
  );
}
