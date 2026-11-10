// URLs: English at the root (/library/29), Arabic under /ar (/ar/library/29).
// src/proxy.ts maps the unprefixed URLs to the [lang] routes.

export type Lang = "en" | "ar";
export const LANGS: Lang[] = ["en", "ar"];
export const LANG_COOKIE = "marjaa.lang";

export const isLang = (v: string | undefined): v is Lang => v === "en" || v === "ar";
export const dirOf = (lang: Lang) => (lang === "ar" ? "rtl" : "ltr");

/** Remove a leading /en or /ar: "/ar/library/3" -> "/library/3". */
export function stripLocale(pathname: string): string {
  const stripped = pathname.replace(/^\/(en|ar)(?=\/|$)/, "");
  return stripped || "/";
}

/** The public URL of `path` in `lang`: ("ar", "/library") -> "/ar/library". */
export function localePath(lang: Lang, path: string): string {
  const clean = stripLocale(path.startsWith("/") ? path : `/${path}`);
  if (lang === "en") return clean;
  return clean === "/" ? "/ar" : `/ar${clean}`;
}

/** The language a public pathname belongs to. */
export const langOfPath = (pathname: string): Lang => (/^\/ar(\/|$)/.test(pathname) ? "ar" : "en");
