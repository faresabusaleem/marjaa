import type { MetadataRoute } from "next";
import { SITE_URL } from "@/lib/i18n";
import { ARTICLES } from "@/lib/law";
import { localePath } from "@/lib/locale";

export default function sitemap(): MetadataRoute.Sitemap {
  const paths = ["/", "/library", "/library/preamble", ...ARTICLES.map((a) => `/library/${a.n}`), "/how-it-works", "/about"];
  return paths.map((path) => ({
    url: `${SITE_URL}${localePath("en", path)}`,
    alternates: { languages: { en: `${SITE_URL}${localePath("en", path)}`, ar: `${SITE_URL}${localePath("ar", path)}` } },
  }));
}
