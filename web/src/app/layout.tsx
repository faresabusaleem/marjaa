import type { Metadata, Viewport } from "next";
import { IBM_Plex_Sans, IBM_Plex_Sans_Arabic, Newsreader, Noto_Naskh_Arabic } from "next/font/google";
import { Header } from "@/components/Header";
import { PREFS_SCRIPT, PrefsProvider } from "@/components/Prefs";
import "./globals.css";

// Interface: IBM Plex Sans (Latin + Arabic). Law text and answers: a reading
// serif, Newsreader for English and Noto Naskh for Arabic.
const plex = IBM_Plex_Sans({ subsets: ["latin"], weight: ["400", "500", "600"], variable: "--font-plex" });
const plexArabic = IBM_Plex_Sans_Arabic({
  subsets: ["arabic"],
  weight: ["400", "500", "600"],
  variable: "--font-plex-arabic",
});
const newsreader = Newsreader({ subsets: ["latin"], variable: "--font-newsreader" });
const naskh = Noto_Naskh_Arabic({ subsets: ["arabic"], variable: "--font-naskh" });

export const metadata: Metadata = {
  title: "Marjaa · مرجع — cited answers on UAE Labour Law",
  description:
    "Ask about the UAE Federal Labour Law in Arabic or English. Every answer cites the exact article, checked in code; out-of-scope questions get “not found”.",
  openGraph: {
    title: "Marjaa · مرجع",
    description: "Cited answers on the UAE Labour Law, in Arabic and English.",
    type: "website",
  },
};

export const viewport: Viewport = {
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#f6f4ef" },
    { media: "(prefers-color-scheme: dark)", color: "#0e1114" },
  ],
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  const fonts = [plex, plexArabic, newsreader, naskh].map((f) => f.variable).join(" ");
  return (
    <html lang="en" dir="ltr" className={fonts} suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: PREFS_SCRIPT }} />
      </head>
      <body className="min-h-dvh">
        <PrefsProvider>
          <Header />
          {children}
        </PrefsProvider>
      </body>
    </html>
  );
}
