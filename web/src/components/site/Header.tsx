"use client";

import { Menu, X } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { REPO_URL } from "@/lib/i18n";
import { LANG_COOKIE, localePath, stripLocale } from "@/lib/locale";
import { HeaderLockup } from "../brand/Logo";
import { GithubMark } from "./GithubMark";
import { useLang, useT } from "./LangProvider";
import { ThemeToggle } from "./ThemeToggle";

const ICON_BUTTON =
  "grid size-10 place-items-center rounded-md text-ink-muted transition-colors hover:bg-surface hover:text-ink active:bg-surface-strong";

export function Header() {
  const lang = useLang();
  const t = useT();
  const pathname = usePathname();
  const path = stripLocale(pathname);
  const [open, setOpen] = useState(false);

  useEffect(() => setOpen(false), [pathname]);
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setOpen(false);
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open]);

  const nav = [
    { href: "/", label: t.nav.ask },
    { href: "/library", label: t.nav.library },
    { href: "/how-it-works", label: t.nav.how },
    { href: "/about", label: t.nav.about },
  ];
  const active = (href: string) => (href === "/" ? path === "/" : path === href || path.startsWith(`${href}/`));
  const other = lang === "en" ? "ar" : "en";

  // Remember the choice so "/" opens in this language next time (src/proxy.ts).
  const rememberOther = () => {
    document.cookie = `${LANG_COOKIE}=${other}; path=/; max-age=31536000; samesite=lax`;
  };

  return (
    <header className="relative z-30 border-b border-line bg-bg">
      <a
        href="#content"
        className="sr-only focus:not-sr-only focus:absolute focus:start-4 focus:top-3 focus:z-50 focus:rounded-md focus:bg-accent-fill focus:px-4 focus:py-2 focus:text-on-accent"
      >
        {t.nav.skip}
      </a>
      <div className="mx-auto flex h-16 max-w-[76rem] items-center gap-4 px-5 sm:px-8">
        <Link href={localePath(lang, "/")} aria-label={t.nav.home} className="-m-1 shrink-0 rounded-sm p-1">
          <HeaderLockup animate className="h-[1.9rem] w-auto" />
        </Link>

        <nav aria-label={t.nav.main} className="ms-6 hidden h-full items-stretch md:flex">
          {nav.map((n) => (
            <Link
              key={n.href}
              href={localePath(lang, n.href)}
              aria-current={active(n.href) ? "page" : undefined}
              className={`relative flex items-center px-3 text-small transition-colors after:absolute after:inset-x-3 after:-bottom-px after:h-0.5 ${
                active(n.href) ? "font-medium text-ink after:bg-brand-sea" : "text-ink-muted hover:text-ink"
              }`}
            >
              {n.label}
            </Link>
          ))}
        </nav>

        <div className="ms-auto flex items-center gap-1">
          <Link
            href={localePath(other, path)}
            onClick={rememberOther}
            lang={other}
            hrefLang={other}
            title={t.nav.switchLangLabel}
            className="rounded-md px-3 py-2 text-small font-medium text-ink transition-colors hover:bg-surface"
          >
            {t.nav.switchLang}
          </Link>
          <ThemeToggle className={ICON_BUTTON} />
          <a href={REPO_URL} target="_blank" rel="noreferrer" aria-label={t.nav.github} title={t.nav.github} className={`${ICON_BUTTON} hidden sm:grid`}>
            <GithubMark size={18} />
          </a>
          <button
            type="button"
            onClick={() => setOpen((v) => !v)}
            aria-expanded={open}
            aria-controls="mobile-nav"
            aria-label={open ? t.nav.closeMenu : t.nav.menu}
            className={`${ICON_BUTTON} md:hidden`}
          >
            {open ? <X size={20} strokeWidth={1.75} aria-hidden /> : <Menu size={20} strokeWidth={1.75} aria-hidden />}
          </button>
        </div>
      </div>

      {open && (
        <nav
          id="mobile-nav"
          aria-label={t.nav.main}
          className="sheet-in absolute inset-x-0 top-full border-b border-line bg-bg px-5 pb-6 pt-2 shadow-float md:hidden"
        >
          <ul>
            {nav.map((n) => (
              <li key={n.href}>
                <Link
                  href={localePath(lang, n.href)}
                  aria-current={active(n.href) ? "page" : undefined}
                  className={`flex items-center justify-between border-b border-line py-3.5 text-lead ${
                    active(n.href) ? "font-medium text-ink" : "text-ink-muted"
                  }`}
                >
                  {n.label}
                  {active(n.href) && <span className="size-1.5 rounded-full bg-brand-sea" aria-hidden />}
                </Link>
              </li>
            ))}
          </ul>
          <a href={REPO_URL} target="_blank" rel="noreferrer" className="mt-5 inline-flex items-center gap-2 text-small text-ink-muted">
            <GithubMark size={16} /> {t.nav.github}
          </a>
        </nav>
      )}
    </header>
  );
}
