import { useId } from "react";
import { BIG_TRIANGLE, LOGOS, SMALL_TRIANGLE, TILE } from "./glyphs";

// The logo as drawn by scripts/build_brand.py, coloured by the theme tokens
// (fill-brand-ink, fill-brand-sea, fill-brand-gold), so it follows dark mode.

interface Props {
  className?: string;
  /** Draw the Sadu band in, tile by tile (once, on first load). */
  animate?: boolean;
  title?: string;
}

function Svg({ logo, className, animate, title }: Props & { logo: (typeof LOGOS)[keyof typeof LOGOS] }) {
  return (
    <svg
      viewBox={`0 0 ${logo.width} ${logo.height}`}
      className={`${animate ? "sadu-draw " : ""}${className ?? ""}`}
      role={title ? "img" : undefined}
      aria-label={title}
      aria-hidden={title ? undefined : true}
      focusable="false"
      dangerouslySetInnerHTML={{ __html: logo.markup }}
    />
  );
}

/** Header lockup: مرجع over a thin Sea band, MARJAA beside it. */
export function HeaderLockup(props: Props) {
  return <Svg logo={LOGOS.header} {...props} />;
}

/** Primary logo: مرجع, the Sadu band, MARJAA. */
export function PrimaryLogo(props: Props) {
  return <Svg logo={LOGOS.primary} {...props} />;
}

/**
 * A full-width Sadu band, repeated as an SVG pattern. `tile` is the tile width
 * in px; the height follows the 20 x 18 tile.
 */
export function SaduBand({ tile = 18, className, single }: { tile?: number; className?: string; single?: boolean }) {
  const id = useId();
  const k = tile / TILE.w;
  const h = TILE.h * k;
  return (
    <svg className={className} width="100%" height={h} aria-hidden="true" focusable="false">
      <defs>
        <pattern id={id} width={tile} height={h} patternUnits="userSpaceOnUse">
          <polygon points={BIG_TRIANGLE} transform={`scale(${k})`} className="fill-brand-sea" />
          {!single && <polygon points={SMALL_TRIANGLE} transform={`scale(${k})`} className="fill-brand-gold" />}
        </pattern>
      </defs>
      <rect width="100%" height={h} fill={`url(#${id})`} />
    </svg>
  );
}

/** Loading indicator: a short band whose tiles fill one after another. */
export function SaduLoader({ tiles = 7, tile = 14, label }: { tiles?: number; tile?: number; label: string }) {
  const k = tile / TILE.w;
  return (
    <div role="status" className="flex items-center gap-3 text-small text-ink-muted">
      <svg width={tiles * tile} height={TILE.h * k} className="sadu-loading shrink-0" aria-hidden="true" focusable="false">
        {Array.from({ length: tiles }, (_, i) => (
          <g key={i} className="sadu-tile" style={{ ["--i" as string]: i }} transform={`translate(${i * tile} 0) scale(${k})`}>
            <polygon points={BIG_TRIANGLE} className="fill-brand-sea" />
            <polygon points={SMALL_TRIANGLE} className="fill-brand-gold" />
          </g>
        ))}
      </svg>
      <span>{label}</span>
    </div>
  );
}
