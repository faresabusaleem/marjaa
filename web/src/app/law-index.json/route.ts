import { searchIndex } from "@/lib/law";

// The Library's full-text search index, built once at build time.
export const dynamic = "force-static";

export function GET() {
  return Response.json(searchIndex());
}
