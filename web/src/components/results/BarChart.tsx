// A single-series horizontal bar chart: one hue (Sea), thin bars anchored at
// zero with a rounded data end, recessive gridlines, the value in text colour
// at the bar end, a tooltip per bar, and a table for screen readers. Bars grow
// from the start edge, so they mirror in Arabic.

interface Row {
  label: string;
  value: number | null; // 0..1
}

const TICKS = [0, 0.25, 0.5, 0.75, 1];

export function BarChart({ title, caption, rows, notMeasured }: { title: string; caption?: string; rows: Row[]; notMeasured: string }) {
  const pct = (v: number) => `${(v * 100).toFixed(1)}%`;
  return (
    <figure className="rounded-lg bg-surface p-5 sm:p-7">
      <figcaption>
        <p className="font-semibold text-ink">{title}</p>
        {caption && <p className="mt-1 text-small text-ink-muted">{caption}</p>}
      </figcaption>
      <div className="mt-6 grid grid-cols-[minmax(6.5rem,9.5rem)_minmax(0,1fr)] gap-x-4 gap-y-3" aria-hidden="true">
        {rows.map((r) => (
          <div key={r.label} className="group contents">
            <div className="self-center text-small leading-snug text-ink-muted group-hover:text-ink">{r.label}</div>
            {/* The plot stops 3.75rem short of the edge so every value label fits after its bar. */}
            <div className="relative me-15 h-8" title={r.value === null ? `${r.label}: ${notMeasured}` : `${r.label}: ${pct(r.value)}`}>
              {TICKS.map((t) => (
                <span key={t} className="absolute inset-y-0 w-px bg-chart-track" style={{ insetInlineStart: `${t * 100}%` }} />
              ))}
              {r.value !== null ? (
                <>
                  <span
                    className="absolute top-1/2 h-3.5 -translate-y-1/2 rounded-e-[4px] bg-chart transition-opacity group-hover:opacity-80"
                    style={{ insetInlineStart: 0, width: `${Math.max(r.value * 100, 0.5)}%` }}
                  />
                  <span
                    className="tabular absolute top-1/2 -translate-y-1/2 whitespace-nowrap ps-2 text-small font-medium text-ink"
                    style={{ insetInlineStart: `${r.value * 100}%` }}
                  >
                    <bdi dir="ltr">{pct(r.value)}</bdi>
                  </span>
                </>
              ) : (
                <span className="absolute top-1/2 -translate-y-1/2 text-small text-ink-muted">{notMeasured}</span>
              )}
            </div>
          </div>
        ))}
        <div />
        <div className="tabular relative me-15 h-4 text-[11px] text-ink-muted">
          {TICKS.map((t) => (
            <span key={t} className="absolute -translate-x-1/2 rtl:translate-x-1/2" style={{ insetInlineStart: `${t * 100}%` }}>
              <bdi dir="ltr">{t * 100}%</bdi>
            </span>
          ))}
        </div>
      </div>
      <table className="sr-only">
        <caption>{title}</caption>
        <tbody>
          {rows.map((r) => (
            <tr key={r.label}>
              <th scope="row">{r.label}</th>
              <td>{r.value === null ? notMeasured : pct(r.value)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </figure>
  );
}
