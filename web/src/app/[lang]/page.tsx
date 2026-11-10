import type { Metadata } from "next";
import { Chat } from "@/components/ask/Chat";
import { ARTICLES } from "@/lib/law";
import { isLang } from "@/lib/locale";
import { pageMetadata } from "@/lib/metadata";
import { headline } from "@/lib/results";

export async function generateMetadata({ params }: PageProps<"/[lang]">): Promise<Metadata> {
  const { lang } = await params;
  return pageMetadata(isLang(lang) ? lang : "en", "/");
}

/** Long articles are split into parts (-p0, -p1, …); the article panel needs the count. */
function multipartArticles(): Record<string, number> {
  const parts: Record<string, number> = {};
  for (const a of ARTICLES) {
    for (const v of [a.ar, a.en]) {
      if (v.chunks.length > 1) parts[v.chunks[0].replace(/-p\d+$/, "")] = v.chunks.length;
    }
  }
  return parts;
}

export default function AskPage() {
  return <Chat headline={{ ...headline(), articles: ARTICLES.length }} parts={multipartArticles()} />;
}
