import type { Metadata, Viewport } from "next";
import { IBM_Plex_Mono, IBM_Plex_Sans, IBM_Plex_Sans_Arabic, Reem_Kufi } from "next/font/google";
import { notFound } from "next/navigation";
import { Footer } from "@/components/site/Footer";
import { Header } from "@/components/site/Header";
import { LangProvider } from "@/components/site/LangProvider";
import { THEME_SCRIPT } from "@/components/site/ThemeToggle";
import { SITE_URL, STRINGS } from "@/lib/i18n";
import { dirOf, isLang, LANGS } from "@/lib/locale";
import "../globals.css";

// IBM Plex Sans and Plex Sans Arabic were drawn as one family, so Latin and
// Arabic sit together evenly. Reem Kufi is for the logo and large Arabic
// display headings only; Plex Mono for citation references.
const plex = IBM_Plex_Sans({ subsets: ["latin"], weight: ["400", "500", "600"], variable: "--font-plex" });
const plexArabic = IBM_Plex_Sans_Arabic({ subsets: ["arabic"], weight: ["400", "500", "600"], variable: "--font-plex-arabic" });
const reem = Reem_Kufi({ subsets: ["arabic"], weight: ["700"], variable: "--font-reem", preload: false });
const mono = IBM_Plex_Mono({ subsets: ["latin"], weight: ["500"], variable: "--font-plex-mono", preload: false });

export const dynamicParams = false;
export function generateStaticParams() {
  return LANGS.map((lang) => ({ lang }));
}

export async function generateMetadata({ params }: LayoutProps<"/[lang]">): Promise<Metadata> {
  const { lang } = await params;
  const t = STRINGS[isLang(lang) ? lang : "en"];
  return {
    metadataBase: new URL(SITE_URL),
    title: { default: t.meta.title, template: `%s · ${t.meta.siteName}` },
    description: t.meta.description,
    applicationName: t.meta.siteName,
    icons: {
      icon: [
        { url: "/favicon.ico", sizes: "48x48" },
        { url: "/brand/favicon.svg", type: "image/svg+xml" },
      ],
      apple: { url: "/brand/apple-touch-icon.png", sizes: "180x180" },
    },
  };
}

// Pearl and the dark ground (src/app/tokens.css), for the browser chrome.
export const viewport: Viewport = {
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#faf7f1" },
    { media: "(prefers-color-scheme: dark)", color: "#1e150e" },
  ],
};

export default async function RootLayout({ children, params }: LayoutProps<"/[lang]">) {
  const { lang } = await params;
  if (!isLang(lang)) notFound();
  const fonts = [plex, plexArabic, reem, mono].map((f) => f.variable).join(" ");
  return (
    <html lang={lang} dir={dirOf(lang)} className={fonts} suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: THEME_SCRIPT }} />
      </head>
      <body className="flex min-h-dvh flex-col">
        <LangProvider lang={lang}>
          <Header />
          <main id="content" className="flex flex-1 flex-col">
            {children}
          </main>
          <Footer lang={lang} />
        </LangProvider>
      </body>
    </html>
  );
}
