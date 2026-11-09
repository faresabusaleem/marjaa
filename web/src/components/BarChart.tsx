// A single-series horizontal bar chart: one hue, thin bars anchored at zero
// with a rounded data end, recessive gridlines, values in text colour at the
// bar end, a hover tooltip per bar, and a screen-reader table.

interface Row {
  label: string;
  value: number | null; // 0..1
  detail?: string;
}

const TICKS = [0, 0.25, 0.5, 0.75, 1];

export function BarChart({ title, caption, rows }: { title: string; caption?: string; rows: Row[] }) {
  const pct = (v: number) => `${(v * 100).toFixed(1)}%`;
  return (
    <figure className="rounded-2xl border border-line bg-surface p-5 sm:p-6">
      <figcaption className="mb-4">
        <p className="font-medium">{title}</p>
        {caption && <p className="mt-0.5 text-sm text-muted">{caption}</p>}
      </figcaption>
      <div className="grid grid-cols-[minmax(7rem,10rem)_1fr] gap-x-4 gap-y-2.5" aria-hidden="true">
        {rows.map((r) => (
          <div key={r.label} className="group contents">
            <div className="self-center text-sm text-muted group-hover:text-ink">{r.label}</div>
            {/* The plot stops 3.5rem short of the edge so every value label fits after its bar. */}
            <div
              className="relative me-14 h-7"
              title={r.value === null ? `${r.label}: not measured` : `${r.label}: ${pct(r.value)}${r.detail ? ` (${r.detail})` : ""}`}
            >
              {TICKS.map((t) => (
                <span key={t} className="absolute inset-y-0 w-px bg-line" style={{ left: `${t * 100}%` }} />
              ))}
              {r.value !== null && (
                <>
                  <span
                    className="absolute left-0 top-1/2 h-3.5 -translate-y-1/2 rounded-e-[4px] bg-chart transition-opacity group-hover:opacity-80"
                    style={{ width: `${Math.max(r.value * 100, 0.5)}%` }}
                  />
                  <span
                    className="absolute top-1/2 -translate-y-1/2 whitespace-nowrap ps-2 text-sm tabular-nums text-ink"
                    style={{ left: `${r.value * 100}%` }}
                  >
                    {pct(r.value)}
                  </span>
                </>
              )}
              {r.value === null && <span className="absolute top-1/2 -translate-y-1/2 text-sm text-faint">—</span>}
            </div>
          </div>
        ))}
        <div />
        <div className="relative me-14 h-4 text-[11px] tabular-nums text-faint">
          {TICKS.map((t) => (
            <span key={t} className="absolute -translate-x-1/2" style={{ left: `${t * 100}%` }}>
              {t * 100}%
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
              <td>{r.value === null ? "not measured" : pct(r.value)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </figure>
  );
}
