import type { Metadata } from "next";
import { SITE_URL, STRINGS } from "./i18n";
import { type Lang, localePath } from "./locale";

/** Title, description, canonical URL and its other-language alternate for a page. */
export function pageMetadata(lang: Lang, path: string, title?: string, description?: string): Metadata {
  const t = STRINGS[lang];
  const url = localePath(lang, path);
  return {
    title: title ?? { absolute: t.meta.title },
    description: description ?? t.meta.description,
    alternates: {
      canonical: url,
      languages: { en: localePath("en", path), ar: localePath("ar", path), "x-default": localePath("en", path) },
    },
    openGraph: {
      title: title ? `${title} · ${t.meta.siteName}` : t.meta.title,
      description: description ?? t.meta.description,
      url: `${SITE_URL}${url}`,
      siteName: t.meta.siteName,
      locale: lang === "ar" ? "ar_AE" : "en_AE",
      type: "website",
      images: [{ url: "/brand/og.png", width: 1200, height: 630, alt: "Marjaa · مرجع" }],
    },
    twitter: { card: "summary_large_image" },
  };
}
