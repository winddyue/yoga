// 金额格式化：分 → "¥x.xx"
function fmtYuan(cents) {
  const n = Number(cents) || 0;
  return '¥' + (n / 100).toFixed(2);
}

module.exports = { fmtYuan };
