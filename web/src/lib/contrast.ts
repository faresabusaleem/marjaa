// WCAG 2 contrast for the design tokens in src/app/tokens.css.

/** Relative luminance of a #rrggbb colour. */
export function luminance(hex: string): number {
  const [r, g, b] = [1, 3, 5].map((i) => {
    const c = parseInt(hex.slice(i, i + 2), 16) / 255;
    return c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
  });
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}

export function contrast(a: string, b: string): number {
  const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x);
  return (hi + 0.05) / (lo + 0.05);
}

export type Theme = "light" | "dark";

/**
 * Read the custom properties of tokens.css into a resolved {name: #hex} map per
 * theme. `:root` blocks give the light values; `.dark` overrides them.
 */
export function readTokens(css: string): Record<Theme, Record<string, string>> {
  const text = css.replace(/\/\*[\s\S]*?\*\//g, "");
  const light: Record<string, string> = {};
  const dark: Record<string, string> = {};
  for (const block of text.matchAll(/([^{}]+)\{([^{}]*)\}/g)) {
    const selector = block[1].trim();
    const target = selector === ":root" ? light : selector === ".dark" ? dark : null;
    if (!target) continue;
    for (const decl of block[2].matchAll(/--([\w-]+)\s*:\s*([^;]+);/g)) target[decl[1]] = decl[2].trim();
  }
  const resolve = (vars: Record<string, string>, value: string, depth = 0): string => {
    const ref = value.match(/^var\(--([\w-]+)\)$/);
    if (!ref) return value.toLowerCase();
    if (depth > 10 || !(ref[1] in vars)) throw new Error(`unresolved token ${value}`);
    return resolve(vars, vars[ref[1]], depth + 1);
  };
  const out = { light: {}, dark: {} } as Record<Theme, Record<string, string>>;
  const themes: [Theme, Record<string, string>][] = [
    ["light", light],
    ["dark", { ...light, ...dark }],
  ];
  for (const [theme, vars] of themes) {
    for (const name of Object.keys(vars)) {
      const v = resolve(vars, vars[name]);
      if (/^#[0-9a-f]{6}$/.test(v)) out[theme][name] = v;
    }
  }
  return out;
}

/** Text/background pairs that must pass (4.5:1 text, 3:1 non-text: borders, focus, bars). */
export const PAIRS: { fg: string; bg: string[]; min: number; use: string }[] = [
  { fg: "ink", bg: ["bg", "surface", "surface-strong"], min: 4.5, use: "Body text" },
  { fg: "ink-muted", bg: ["bg", "surface", "surface-strong"], min: 4.5, use: "Secondary text" },
  { fg: "ink-faint", bg: ["bg", "surface"], min: 4.5, use: "Captions, placeholders" },
  { fg: "accent", bg: ["bg", "surface", "accent-subtle"], min: 4.5, use: "Links, accent text" },
  { fg: "on-accent", bg: ["accent-fill", "accent-fill-hover", "accent-fill-press"], min: 4.5, use: "Button labels" },
  { fg: "warn", bg: ["bg", "warn-subtle"], min: 4.5, use: "Warnings" },
  { fg: "danger", bg: ["bg", "danger-subtle"], min: 4.5, use: "Errors" },
  { fg: "brand-ink", bg: ["bg", "surface"], min: 4.5, use: "Wordmark" },
  { fg: "focus", bg: ["bg", "surface"], min: 3, use: "Focus ring" },
  { fg: "line-strong", bg: ["bg", "surface"], min: 3, use: "Form field borders" },
  { fg: "chart", bg: ["bg", "surface"], min: 3, use: "Chart bars" },
  { fg: "brand-sea", bg: ["bg", "surface"], min: 3, use: "Sadu band" },
];
