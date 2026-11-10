"use client";

import { Moon, Sun } from "lucide-react";
import { useEffect, useState } from "react";
import { useT } from "./LangProvider";

const KEY = "marjaa.theme";

// Runs in <head> before first paint, so the page never flashes the wrong theme.
export const THEME_SCRIPT = `(function(){try{var t=localStorage.getItem('${KEY}');if(t?t==='dark':matchMedia('(prefers-color-scheme: dark)').matches)document.documentElement.classList.add('dark')}catch(e){}})()`;

function stored(): string | null {
  try {
    return localStorage.getItem(KEY);
  } catch {
    return null;
  }
}

export function ThemeToggle({ className }: { className?: string }) {
  const t = useT();
  const [dark, setDark] = useState(false);

  useEffect(() => {
    setDark(document.documentElement.classList.contains("dark"));
    // With no choice saved, keep following the system setting.
    const media = matchMedia("(prefers-color-scheme: dark)");
    const follow = (e: MediaQueryListEvent) => {
      if (stored()) return;
      document.documentElement.classList.toggle("dark", e.matches);
      setDark(e.matches);
    };
    media.addEventListener("change", follow);
    return () => media.removeEventListener("change", follow);
  }, []);

  const toggle = () => {
    const next = !dark;
    document.documentElement.classList.toggle("dark", next);
    try {
      localStorage.setItem(KEY, next ? "dark" : "light");
    } catch {
      // Storage blocked: the choice lasts for this page only.
    }
    setDark(next);
  };

  const label = dark ? t.nav.light : t.nav.dark;
  return (
    <button type="button" onClick={toggle} aria-label={label} title={label} className={className}>
      {dark ? <Sun size={18} strokeWidth={1.75} aria-hidden /> : <Moon size={18} strokeWidth={1.75} aria-hidden />}
    </button>
  );
}
