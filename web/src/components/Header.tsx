"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { REPO_URL } from "@/lib/i18n";
import { GitHub, Logo, Moon, Sun } from "./Icons";
import { usePrefs } from "./Prefs";

export function Header() {
  const { t, lang, setLang, dark, toggleDark } = usePrefs();
  const path = usePathname();
  const nav = [
    { href: "/", label: t.ask },
    { href: "/about", label: t.howItWorks },
  ];
  return (
    <header className="sticky top-0 z-30 border-b border-line bg-bg/85 backdrop-blur supports-[backdrop-filter]:bg-bg/70">
      <div className="mx-auto flex h-14 max-w-6xl items-center gap-3 px-4 sm:px-6">
        <Link href="/" className="flex items-center gap-2.5 rounded-md" aria-label="Marjaa home">
          <Logo />
          <span className="flex items-baseline gap-1.5">
            <span className="font-read text-[1.35rem] font-semibold tracking-tight" lang="en">
              Marjaa
            </span>
            <span className="font-read hidden text-lg text-muted min-[400px]:inline" lang="ar">
              مرجع
            </span>
          </span>
        </Link>

        <nav className="ms-4 hidden items-center gap-1 sm:flex" aria-label="Main">
          {nav.map((n) => (
            <Link
              key={n.href}
              href={n.href}
              className={`rounded-md px-3 py-1.5 text-sm transition-colors ${
                path === n.href ? "bg-surface-2 text-ink" : "text-muted hover:text-ink"
              }`}
            >
              {n.label}
            </Link>
          ))}
        </nav>

        <div className="ms-auto flex items-center gap-1">
          <Link
            href={path === "/about" ? "/" : "/about"}
            className="whitespace-nowrap rounded-md px-2.5 py-1.5 text-sm text-muted hover:text-ink sm:hidden"
          >
            {path === "/about" ? t.ask : t.howItWorks}
          </Link>
          <button
            type="button"
            onClick={() => setLang(lang === "en" ? "ar" : "en")}
            className="rounded-md px-2.5 py-1.5 text-sm text-muted hover:bg-surface-2 hover:text-ink"
            lang={lang === "en" ? "ar" : "en"}
          >
            {t.switchLang}
          </button>
          <button
            type="button"
            onClick={toggleDark}
            className="grid size-9 place-items-center rounded-md text-muted hover:bg-surface-2 hover:text-ink"
            aria-label={t.theme}
            title={t.theme}
          >
            {dark ? <Sun /> : <Moon />}
          </button>
          <a
            href={REPO_URL}
            target="_blank"
            rel="noreferrer"
            className="grid size-9 place-items-center rounded-md text-muted hover:bg-surface-2 hover:text-ink"
            aria-label={t.github}
            title={t.github}
          >
            <GitHub />
          </a>
        </div>
      </div>
    </header>
  );
}
