const { syncTheme } = require('../../utils/themes.js');
// 用户协议 / 隐私政策：登录页勾选处可点开查看
Page({
  onShow() { syncTheme(this); },
  data: {
    tab: 'privacy',   // privacy=隐私政策 | terms=用户协议
    updated: '2026-10-07',
  },

  onLoad(options) {
    if (options && options.tab === 'terms') this.setData({ tab: 'terms' });
  },

  switchTab(e) {
    this.setData({ tab: e.currentTarget.dataset.t });
    wx.pageScrollTo({ scrollTop: 0, duration: 0 });
  },

  back() { wx.navigateBack(); },
});
