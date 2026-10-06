const api = require('../../api.js');
Page({
  data: { user: null },
  async onShow() {
    const user = getApp().globalData.user || await api.get('/api/auth/me');
    this.setData({ user });
  },
  logout() { api.logout(); },
});
