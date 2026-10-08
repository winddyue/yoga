// 练后对比：取 trends 数组最后两个有效值，算"较上次"差值。
// 四个指标都是下降=好（绿）、上升=差（红）、持平=null（灰）。
const UNITS = { weight: 'kg', body_fat: '%', waist: 'cm', hip: 'cm' };

function lastDelta(trends, metric) {
  const arr = (trends && trends[metric]) || [];
  // 从后往前取最后两个有效值（跳过 null/undefined/0/负数）
  const vals = [];
  for (let i = arr.length - 1; i >= 0 && vals.length < 2; i--) {
    const v = arr[i];
    if (typeof v === 'number' && !isNaN(v) && v > 0) vals.unshift(v);
  }
  // 数据不足（少于两个有效点）：返回 null，调用方不显示
  if (vals.length < 2) return null;
  const diff = +(vals[1] - vals[0]).toFixed(1);
  const unit = UNITS[metric] || '';
  const sign = diff > 0 ? '+' : '';
  return {
    diff,
    text: `${sign}${diff.toFixed(1)}${unit}`,
    better: diff < 0 ? true : (diff > 0 ? false : null),
  };
}

// chip 颜色类：good 绿 / bad 红 / flat 灰；null 数据时返回 ''（不显示）
function deltaCls(d) {
  if (!d) return '';
  return d.better === true ? 'good' : (d.better === false ? 'bad' : 'flat');
}

module.exports = { lastDelta, deltaCls };
