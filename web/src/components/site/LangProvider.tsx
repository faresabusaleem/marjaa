"use client";

import { createContext, useContext } from "react";
import { STRINGS, type Strings } from "@/lib/i18n";
import type { Lang } from "@/lib/locale";

const LangContext = createContext<Lang>("en");

export function LangProvider({ lang, children }: { lang: Lang; children: React.ReactNode }) {
  return <LangContext.Provider value={lang}>{children}</LangContext.Provider>;
}

export const useLang = () => useContext(LangContext);
export const useT = (): Strings => STRINGS[useContext(LangContext)];
