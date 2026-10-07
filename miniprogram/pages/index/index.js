const api = require('../../api.js');

Page({
  data: { s: null, user: null, loading: true, loadErr: '', needLogin: false },

  onShow() { this.load(); },

  async load() {
    this.setData({ loading: true, loadErr: '', needLogin: false });
    try {
      const user = getApp().globalData.user || await api.get('/api/auth/me');
      getApp().globalData.user = user;
      this.setData({ user });
      const url = user.role === 'client' ? '/api/dashboard/me/summary'
        : user.role === 'owner' ? '/api/dashboard/owner/overview'
        : '/api/dashboard/coach/overview';
      const s = await api.get(url);
      this.setData({ s, loading: false });
    } catch (e) {
      // 未登录不是错误：展示登录引导，不弹错、不强制跳转
      if (e.message === '未登录') {
        this.setData({ loading: false, needLogin: true, user: null });
        return;
      }
      this.setData({ loading: false, loadErr: e.message });
    }
  },

  goLogin() { wx.navigateTo({ url: '/pages/auth/auth' }); },
  goBooking() { wx.switchTab({ url: '/pages/booking/booking' }); },
});
