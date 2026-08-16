type SeriesItem = {
  clave: string;
  valor: number;
  color?: string;
};

type BarChartProps = {
  title: string;
  subtitle?: string;
  data: SeriesItem[];
  maxBars?: number;
  valueFormatter?: (n: number) => string;
};

const PALETTE = ["#4f46e5", "#06b6d4", "#f59e0b", "#f43f5e", "#8b5cf6", "#10b981", "#3b82f6", "#ec4899"];

export function BarChart({ title, subtitle, data, maxBars = 12, valueFormatter }: BarChartProps) {
  const rows = data.slice(0, maxBars);
  const max = Math.max(1, ...rows.map((d) => Math.abs(d.valor)));
  const fmt = valueFormatter ?? ((n: number) => String(n));

  return (
    <div className="panel chart-panel">
      <div className="chart-head">
        <h3>{title}</h3>
        {subtitle && <p className="muted">{subtitle}</p>}
      </div>
      {rows.length === 0 ? (
        <p className="muted empty-inline">Sin datos para este gráfico todavía</p>
      ) : (
        <div className="bar-list">
          {rows.map((row, idx) => (
            <div className="bar-row" key={`${row.clave}-${idx}`}>
              <div className="bar-label" title={row.clave}>
                {row.clave}
              </div>
              <div className="bar-track">
                <div
                  className="bar-fill animate-bar"
                  style={{
                    width: `${(Math.abs(row.valor) / max) * 100}%`,
                    background: row.color ?? PALETTE[idx % PALETTE.length],
                  }}
                  title={`${row.clave}: ${fmt(row.valor)}`}
                />
              </div>
              <div className="bar-value mono">{fmt(row.valor)}</div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export function DonutChart({
  title,
  subtitle,
  data,
}: {
  title: string;
  subtitle?: string;
  data: SeriesItem[];
}) {
  const total = data.reduce((s, d) => s + d.valor, 0);
  const r = 54;
  const c = 2 * Math.PI * r;
  let offset = 0;

  return (
    <div className="panel chart-panel">
      <div className="chart-head">
        <h3>{title}</h3>
        {subtitle && <p className="muted">{subtitle}</p>}
      </div>
      {total <= 0 ? (
        <p className="muted">Sin datos</p>
      ) : (
        <div className="donut-wrap">
          <svg width="140" height="140" viewBox="0 0 140 140">
            <g transform="translate(70,70)">
              {data.map((d, idx) => {
                const len = (d.valor / total) * c;
                const el = (
                  <circle
                    key={d.clave}
                    r={r}
                    fill="transparent"
                    stroke={d.color ?? PALETTE[idx % PALETTE.length]}
                    strokeWidth="16"
                    strokeDasharray={`${len} ${c - len}`}
                    strokeDashoffset={-offset}
                    transform="rotate(-90)"
                  />
                );
                offset += len;
                return el;
              })}
              <text textAnchor="middle" dy="0.35em" className="donut-center">
                {total}
              </text>
            </g>
          </svg>
          <ul className="donut-legend">
            {data.map((d, idx) => (
              <li key={d.clave}>
                <span className="swatch" style={{ background: d.color ?? PALETTE[idx % PALETTE.length] }} />
                <span>{d.clave}</span>
                <strong className="mono">{d.valor}</strong>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

export type TimePoint = {
  clave: string;
  valor: number | null;
  color?: string;
};

export function TimeSeriesChart({
  title,
  subtitle,
  series,
  emptyHint = "Serie aún insuficiente",
}: {
  title: string;
  subtitle?: string;
  series: TimePoint[];
  emptyHint?: string;
}) {
  const values = series.map((s) => s.valor).filter((v): v is number => v != null);
  const max = Math.max(1, ...values, 100);
  const w = 520;
  const h = 160;
  const pad = 24;
  const usable = series.length > 1 ? series.length - 1 : 1;

  const points = series
    .map((s, i) => {
      if (s.valor == null) return null;
      const x = pad + (i / usable) * (w - pad * 2);
      const y = h - pad - (s.valor / max) * (h - pad * 2);
      return `${x},${y}`;
    })
    .filter(Boolean)
    .join(" ");

  return (
    <div className="panel chart-panel chart-wide">
      <div className="chart-head">
        <h3>{title}</h3>
        {subtitle && <p className="muted">{subtitle}</p>}
      </div>
      {values.length === 0 ? (
        <p className="muted">{emptyHint}</p>
      ) : (
        <>
          <svg viewBox={`0 0 ${w} ${h}`} className="timeseries-svg" role="img" aria-label={title}>
            <line x1={pad} y1={h - pad} x2={w - pad} y2={h - pad} stroke="currentColor" opacity="0.2" />
            <line x1={pad} y1={pad} x2={pad} y2={h - pad} stroke="currentColor" opacity="0.2" />
            {points && (
              <polyline fill="none" stroke="#6366f1" strokeWidth="2.5" points={points} />
            )}
            {series.map((s, i) => {
              if (s.valor == null) return null;
              const x = pad + (i / usable) * (w - pad * 2);
              const y = h - pad - (s.valor / max) * (h - pad * 2);
              return (
                <circle
                  key={`${s.clave}-${i}`}
                  cx={x}
                  cy={y}
                  r={4}
                  fill={s.color ?? "#6366f1"}
                >
                  <title>
                    {s.clave}: {s.valor.toFixed(1)}%
                  </title>
                </circle>
              );
            })}
          </svg>
          <div className="timeseries-labels">
            {series.map((s) => (
              <span key={s.clave} className="mono muted" title={s.valor == null ? "Pendiente" : `${s.valor}%`}>
                {s.clave}
              </span>
            ))}
          </div>
        </>
      )}
    </div>
  );
}

export function DivergingBarChart({
  title,
  subtitle,
  data,
  emptyHint = "No hay SHAP agregado para este período",
}: {
  title: string;
  subtitle?: string;
  data: { clave: string; valor: number }[];
  emptyHint?: string;
}) {
  const max = Math.max(0.0001, ...data.map((d) => Math.abs(d.valor)));
  return (
    <div className="panel chart-panel">
      <div className="chart-head">
        <h3>{title}</h3>
        {subtitle && <p className="muted">{subtitle}</p>}
      </div>
      {data.length === 0 ? (
        <p className="muted">{emptyHint}</p>
      ) : (
        <div className="bar-list">
          {data.map((row) => {
            const pct = (Math.abs(row.valor) / max) * 50;
            const aumenta = row.valor >= 0;
            return (
              <div className="bar-row diverging" key={row.clave}>
                <div className="bar-label" title={row.clave}>
                  {row.clave}
                </div>
                <div className="diverging-track">
                  <div className="diverging-mid" />
                  <div
                    className={`diverging-fill ${aumenta ? "aumenta" : "reduce"}`}
                    style={{
                      width: `${pct}%`,
                      [aumenta ? "left" : "right"]: "50%",
                    }}
                  />
                </div>
                <div className="bar-value mono">
                  {row.valor >= 0 ? "+" : ""}
                  {row.valor.toFixed(3)}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
