const api = require('../../api.js');
Page({
  data: { user: null, sub: null },
  async onShow() {
    const user = getApp().globalData.user || await api.get('/api/auth/me');
    this.setData({ user });
    try { this.setData({ sub: await api.get('/api/subscriptions/mine') }); } catch (e) {}
  },
  logout() { api.logout(); },
});
