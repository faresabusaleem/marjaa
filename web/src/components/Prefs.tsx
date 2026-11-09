"use client";

import { createContext, useCallback, useContext, useEffect, useState } from "react";
import type { Lang } from "@/lib/api";
import { STRINGS, type Strings } from "@/lib/i18n";

interface Prefs {
  lang: Lang;
  t: Strings;
  setLang: (lang: Lang) => void;
  dark: boolean;
  toggleDark: () => void;
}

const PrefsContext = createContext<Prefs | null>(null);

function store(key: string, value: string) {
  try {
    localStorage.setItem(key, value);
  } catch {
    // Private mode or blocked storage: the setting just won't persist.
  }
}

// Runs before first paint (inlined in <head>) so there is no theme/direction flash.
export const PREFS_SCRIPT = `(function(){try{var d=document.documentElement;var t=localStorage.getItem('marjaa.theme');if(t?t==='dark':matchMedia('(prefers-color-scheme: dark)').matches)d.classList.add('dark');if(localStorage.getItem('marjaa.lang')==='ar'){d.lang='ar';d.dir='rtl'}}catch(e){}})()`;

export function PrefsProvider({ children }: { children: React.ReactNode }) {
  const [lang, setLangState] = useState<Lang>("en");
  const [dark, setDark] = useState(false);

  useEffect(() => {
    const root = document.documentElement;
    setLangState(root.lang === "ar" ? "ar" : "en");
    setDark(root.classList.contains("dark"));
  }, []);

  const setLang = useCallback((next: Lang) => {
    const root = document.documentElement;
    root.lang = next;
    root.dir = next === "ar" ? "rtl" : "ltr";
    store("marjaa.lang", next);
    setLangState(next);
  }, []);

  const toggleDark = useCallback(() => {
    setDark((was) => {
      document.documentElement.classList.toggle("dark", !was);
      store("marjaa.theme", was ? "light" : "dark");
      return !was;
    });
  }, []);

  return (
    <PrefsContext.Provider value={{ lang, t: STRINGS[lang], setLang, dark, toggleDark }}>
      {children}
    </PrefsContext.Provider>
  );
}

export function usePrefs(): Prefs {
  const prefs = useContext(PrefsContext);
  if (!prefs) throw new Error("usePrefs must be used inside <PrefsProvider>");
  return prefs;
}
