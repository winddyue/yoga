// 极简 SVG 折线图：展示体重/体脂趋势，不引入图表库
export default function TrendChart({ dates, series, unit, color = '#B76E79' }) {
  if (!dates.length) return <div className="text-sm text-clay">暂无数据</div>;
  const W = 560, H = 180, P = 28;
  const vals = series.filter((v) => v > 0);
  const min = Math.min(...vals), max = Math.max(...vals);
  const span = max - min || 1;
  const X = (i) => (dates.length === 1 ? W / 2 : P + (i * (W - 2 * P)) / (dates.length - 1));
  const Y = (v) => H - P - ((v - min) / span) * (H - 2 * P);
  const pts = series.map((v, i) => `${X(i)},${Y(v)}`).join(' ');
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="w-full">
      <polyline points={pts} fill="none" stroke={color} strokeWidth="2" />
      {series.map((v, i) => (
        <g key={i}>
          <circle cx={X(i)} cy={Y(v)} r="3.5" fill={color} />
          <text x={X(i)} y={H - 8} fontSize="10" textAnchor="middle" fill="#9A8F84">
            {dates[i]?.slice(5)}
          </text>
          <text x={X(i)} y={Y(v) - 8} fontSize="10" textAnchor="middle" fill="#4A4239">{v}</text>
        </g>
      ))}
      <text x={P} y={16} fontSize="11" fill="#776A5D">单位：{unit}（{min} ~ {max}）</text>
    </svg>
  );
}
