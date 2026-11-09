import type { NextConfig } from "next";

// In production, Vercel routes /api/* to the Python service before Next.js
// sees it (vercel.json). In development, forward it to the local API instead.
const apiUrl = process.env.MARJAA_API_URL ?? "http://127.0.0.1:8000";

const nextConfig: NextConfig = {
  // Dev server: also accept http://127.0.0.1:3000, not just localhost.
  allowedDevOrigins: ["127.0.0.1"],
  async rewrites() {
    if (process.env.NODE_ENV !== "development") return [];
    return [{ source: "/api/:path*", destination: `${apiUrl}/api/:path*` }];
  },
};

export default nextConfig;
