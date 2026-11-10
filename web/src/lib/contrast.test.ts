import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";
import { contrast, PAIRS, readTokens, type Theme } from "./contrast";

const tokens = readTokens(readFileSync(new URL("../app/tokens.css", import.meta.url), "utf8"));
const THEMES: Theme[] = ["light", "dark"];

describe("design tokens", () => {
  it("keep the brand colours exactly", () => {
    expect(tokens.light).toMatchObject({
      pearl: "#faf7f1",
      sand: "#f3ebdd",
      dune: "#e9dcc4",
      sea: "#4f7c7a",
      "pearl-gold": "#c9a46a",
      date: "#3a2e26",
      "date-muted": "#6b5e52",
    });
  });

  for (const theme of THEMES) {
    for (const pair of PAIRS) {
      for (const bg of pair.bg) {
        it(`${theme}: ${pair.fg} on ${bg} reaches ${pair.min}:1`, () => {
          const fg = tokens[theme][pair.fg];
          const back = tokens[theme][bg];
          expect(fg, pair.fg).toBeDefined();
          expect(back, bg).toBeDefined();
          expect(contrast(fg, back)).toBeGreaterThanOrEqual(pair.min);
        });
      }
    }
  }

  it("dark mode is warm and never black", () => {
    const [r, g, b] = [1, 3, 5].map((i) => parseInt(tokens.dark.bg.slice(i, i + 2), 16));
    expect(r).toBeGreaterThan(b); // brown, not blue-grey
    expect(r + g + b).toBeGreaterThan(30);
  });
});

// REPORT=1 npx vitest run src/lib/contrast.test.ts prints the table in docs/brand.md.
if (process.env.REPORT) {
  const rows = PAIRS.flatMap((p) =>
    p.bg.map((bg) => {
      const cell = (t: Theme) => `${contrast(tokens[t][p.fg], tokens[t][bg]).toFixed(2)}:1`;
      return `| ${p.use} | \`--${p.fg}\` on \`--${bg}\` | ${cell("light")} | ${cell("dark")} | ${p.min}:1 |`;
    }),
  );
  console.log(["| Use | Pair | Light | Dark | Needs |", "|---|---|---|---|---|", ...rows].join("\n"));
}
