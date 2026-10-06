// 统一交互反馈：加载 / 成功 / 失败 / 空态。
// 目标：任何请求失败都有明确提示，杜绝"页面显示成功但实际失败"的误导。
function showLoading(title) {
  wx.showLoading({ title: title || '加载中…', mask: true });
}

function hideLoading() {
  wx.hideLoading();
}

function showSuccess(title) {
  wx.showToast({ title: title || '操作成功', icon: 'success', duration: 1800 });
}

function showError(err, fallback) {
  const msg = (err && err.message) || fallback || '操作失败，请重试';
  wx.showToast({ title: msg, icon: 'none', duration: 2600 });
}

// 包装请求 Promise：自动 loading + 成功/失败提示。
// opts: { loading: '保存中', success: '已保存', silent: true(只 loading 不 toast 错误) }
function withFeedback(promise, opts) {
  const o = opts || {};
  if (o.loading) showLoading(o.loading);
  return promise.then(
    (res) => {
      if (o.loading) hideLoading();
      if (o.success) showSuccess(o.success);
      return res;
    },
    (err) => {
      if (o.loading) hideLoading();
      // 401 已由 api.js 统一处理（清 token 跳登录），这里不重复弹
      if (!o.silent && !(err && err.message === '登录已过期')) showError(err);
      throw err;
    },
  );
}

// 确认弹窗（删除/取消等不可逆操作前）
function confirm(content, title) {
  return new Promise((resolve) => {
    wx.showModal({
      title: title || '确认',
      content,
      success: (res) => resolve(!!res.confirm),
      fail: () => resolve(false),
    });
  });
}

module.exports = { showLoading, hideLoading, showSuccess, showError, withFeedback, confirm };
