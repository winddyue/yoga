const api = require('../../api.js');
Page({
  data: { username: '', password: '', err: '' },
  onInput(e) { this.setData({ [e.currentTarget.dataset.k]: e.detail.value }); },
  async doLogin() {
    try {
      await api.login(this.data.username, this.data.password);
      const user = await api.get('/api/auth/me');
      getApp().globalData.user = user;
      wx.switchTab({ url: '/pages/index/index' });
    } catch (e) { this.setData({ err: e.message }); }
  },
});
