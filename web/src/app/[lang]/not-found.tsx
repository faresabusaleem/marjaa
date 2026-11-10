"use client";

import Link from "next/link";
import { SaduBand } from "@/components/brand/Logo";
import { useLang, useT } from "@/components/site/LangProvider";
import { localePath } from "@/lib/locale";

export default function NotFound() {
  const t = useT();
  const lang = useLang();
  return (
    <div className="mx-auto w-full max-w-[76rem] px-5 pb-32 pt-20 sm:px-8 sm:pt-28">
      <div className="max-w-xl">
        <SaduBand tile={18} className="block w-36" />
        <h1 className="mt-8 text-h1 font-semibold">{t.notFound.title}</h1>
        <p className="mt-4 text-lead text-ink">{t.notFound.body}</p>
        <div className="mt-8 flex flex-wrap gap-3">
          <Link
            href={localePath(lang, "/")}
            className="inline-flex h-11 items-center rounded-md bg-accent-fill px-4 text-small font-medium text-on-accent hover:bg-accent-fill-hover"
          >
            {t.notFound.home}
          </Link>
          <Link
            href={localePath(lang, "/library")}
            className="inline-flex h-11 items-center rounded-md border border-line-strong px-4 text-small font-medium text-ink hover:bg-surface"
          >
            {t.notFound.library}
          </Link>
        </div>
      </div>
    </div>
  );
}
