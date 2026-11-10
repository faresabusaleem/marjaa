import type { MetadataRoute } from "next";

// Colours: Pearl and Sea (src/app/tokens.css).
export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "Marjaa · مرجع",
    short_name: "Marjaa",
    description: "Cited answers on UAE Labour Law, in Arabic and English.",
    start_url: "/",
    display: "standalone",
    background_color: "#faf7f1",
    theme_color: "#4f7c7a",
    icons: [
      { src: "/brand/icon-192.png", sizes: "192x192", type: "image/png" },
      { src: "/brand/icon-512.png", sizes: "512x512", type: "image/png" },
      { src: "/brand/icon.svg", sizes: "any", type: "image/svg+xml" },
    ],
  };
}
