// 极简 SVG 柱状图：展示月度出勤率等，不引入图表库（与 TrendChart.jsx 风格一致）
export default function BarChart({ labels = [], values = [], unit = '', color = '#0d9488' }) {
  if (!labels.length || !values.length) return <div className="text-sm text-gray-400">暂无数据</div>;
  const W = 560, H = 180, P = 28;
  const max = Math.max(...values, 1);
  const n = labels.length;
  const slot = (W - 2 * P) / n;
  const bw = Math.min(46, slot * 0.55);
  const X = (i) => P + slot * i + (slot - bw) / 2;
  const bh = (v) => (v / max) * (H - 2 * P - 16);
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="w-full">
      {values.map((v, i) => (
        <g key={i}>
          <rect x={X(i)} y={H - P - bh(v)} width={bw} height={Math.max(bh(v), 2)}
            rx="3" fill={color} opacity={v > 0 ? 1 : 0.2} />
          <text x={X(i) + bw / 2} y={H - P - bh(v) - 6} fontSize="11"
            textAnchor="middle" fill="#4b5563">{v}{unit}</text>
          <text x={X(i) + bw / 2} y={H - 8} fontSize="10"
            textAnchor="middle" fill="#9ca3af">{labels[i]}</text>
        </g>
      ))}
    </svg>
  );
}
