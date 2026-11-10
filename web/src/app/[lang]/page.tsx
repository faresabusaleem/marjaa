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

export default function AskPage() {
  return <Chat headline={{ ...headline(), articles: ARTICLES.length }} />;
}
