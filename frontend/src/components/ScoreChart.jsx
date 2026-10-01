const W = 600;
const H = 140;
const PAD = 8;

export default function ScoreChart({ clips, threshold }) {
  if (!clips || clips.length === 0) return null;
  const n = clips.length;
  const x = (i) => (n === 1 ? W / 2 : PAD + (i * (W - 2 * PAD)) / (n - 1));
  const y = (s) => H - PAD - s * (H - 2 * PAD);
  const points = clips.map((c, i) => `${x(i)},${y(c.score)}`).join(" ");

  return (
    <svg className="score-chart" viewBox={`0 0 ${W} ${H}`} role="img" aria-label="Anomaly score per clip">
      <line x1={PAD} x2={W - PAD} y1={y(threshold)} y2={y(threshold)} className="chart-threshold" />
      <polyline points={points} className="chart-line" />
      {clips.map((c, i) => (
        <circle
          key={i}
          cx={x(i)}
          cy={y(c.score)}
          r={4}
          className={c.is_anomaly ? "chart-dot chart-dot-anomaly" : "chart-dot"}
        >
          <title>
            {c.start_sec != null ? `${c.start_sec}s - ${c.end_sec}s` : `frames ${c.start_frame}-${c.end_frame}`}
            {` | score ${c.score}`}
          </title>
        </circle>
      ))}
    </svg>
  );
}
