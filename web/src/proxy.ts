import { type NextRequest, NextResponse } from "next/server";
import { LANG_COOKIE } from "@/lib/locale";

// English lives at the root (/library/29) and Arabic under /ar (/ar/library/29).
// The app's routes are app/[lang]/..., so unprefixed URLs are rewritten to /en.
// A visitor who chose Arabic (cookie), or whose browser prefers it on their
// first visit to the home page, is sent to the Arabic page instead.

function prefersArabic(header: string | null): boolean {
  const first = header?.split(",")[0]?.trim().toLowerCase() ?? "";
  return first.startsWith("ar");
}

export function proxy(request: NextRequest) {
  const url = request.nextUrl.clone();
  const { pathname } = url;

  if (pathname === "/en" || pathname.startsWith("/en/")) {
    url.pathname = pathname.slice(3) || "/";
    return NextResponse.redirect(url, 308);
  }
  if (pathname === "/ar" || pathname.startsWith("/ar/")) return NextResponse.next();

  const chosen = request.cookies.get(LANG_COOKIE)?.value;
  const arabic = chosen ? chosen === "ar" : pathname === "/" && prefersArabic(request.headers.get("accept-language"));
  if (arabic) {
    url.pathname = pathname === "/" ? "/ar" : `/ar${pathname}`;
    return NextResponse.redirect(url, 307);
  }
  url.pathname = `/en${pathname === "/" ? "" : pathname}`;
  return NextResponse.rewrite(url);
}

export const config = {
  // Everything except the API, Next.js internals and files with an extension.
  matcher: ["/((?!api/|_next/|.*\\.[a-zA-Z0-9]+$).*)"],
};
