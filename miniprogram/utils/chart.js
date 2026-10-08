// canvas 绘图复用：趋势折线、圆环。不引入第三方库。
// 从 pages/index/index.js 抽出，行为保持一致。
const { getTheme, currentThemeId } = require('./themes.js');

function themeColors() {
  const th = getTheme(currentThemeId());
  return { pri: th.pri, prid: th.prid, acc: th.acc, mut: th.mut, txt: th.txt, line: th.line };
}

// 趋势折线：trends={dates, weight, body_fat, waist, ...}，metric 为要画的 key。
// lineColor 不传则用主题主色。
function drawTrend(page, canvasId, trends, metric, lineColor) {
  try {
    if (!trends || !trends.dates || !trends.dates.length) return;
    const dates = trends.dates;
    const series = trends[metric] || [];
    const c = themeColors();
    const color = lineColor || c.pri;
    const q = wx.createSelectorQuery();
    q.select('#' + canvasId).boundingClientRect();
    q.exec((res) => {
      if (!res || !res[0]) return;
      const W = res[0].width || 300, H = 150;
      const P = 26, top = 18, bottom = 24;
      const vals = series.filter((v) => v > 0);
      if (!vals.length) return;
      const min = Math.min.apply(null, vals), max = Math.max.apply(null, vals);
      const span = (max - min) || 1;
      const X = (i) => (dates.length === 1 ? W / 2 : P + (i * (W - 2 * P)) / (dates.length - 1));
      const Y = (v) => H - bottom - ((v - min) / span) * (H - top - bottom);
      const ctx = wx.createCanvasContext(canvasId, page);
      ctx.clearRect(0, 0, W, H);
      ctx.setStrokeStyle(color);
      ctx.setLineWidth(2);
      ctx.beginPath();
      series.forEach((v, i) => {
        const x = X(i), y = Y(v);
        if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
      });
      ctx.stroke();
      ctx.setFillStyle(color);
      series.forEach((v, i) => {
        const x = X(i), y = Y(v);
        ctx.beginPath();
        ctx.arc(x, y, 3, 0, 2 * Math.PI);
        ctx.fill();
        ctx.setFillStyle(c.mut);
        ctx.setFontSize(9);
        ctx.setTextAlign('center');
        ctx.fillText(String(dates[i]).slice(5), x, H - 8);
        ctx.setFillStyle(c.txt);
        ctx.fillText(String(v), x, y - 8);
        ctx.setFillStyle(color);
      });
      ctx.draw();
    });
  } catch (e) {}
}

// 出勤目标圆环：rate 为 0~1 的出勤率。canvas 固定 120x120（cx=60,cy=60,R=46）。
function drawRing(page, canvasId, rate) {
  try {
    const ctx = wx.createCanvasContext(canvasId, page);
    const cx = 60, cy = 60, R = 46;
    ctx.setLineWidth(12);
    ctx.setLineCap('round');
    const c = themeColors();
    ctx.setStrokeStyle(c.line);
    ctx.beginPath();
    ctx.arc(cx, cy, R, 0, 2 * Math.PI);
    ctx.stroke();
    if (rate > 0) {
      ctx.setStrokeStyle(c.prid);
      ctx.beginPath();
      ctx.arc(cx, cy, R, -Math.PI / 2, -Math.PI / 2 + 2 * Math.PI * Math.min(rate, 1));
      ctx.stroke();
    }
    ctx.draw();
  } catch (e) {}
}

module.exports = { drawTrend, drawRing, themeColors };
