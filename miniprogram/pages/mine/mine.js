const api = require('../../api.js');
const fb = require('../../utils/feedback.js');

Page({
  data: { user: null },
  onShow() {
    api.get('/api/auth/me')
      .then((user) => { getApp().globalData.user = user; this.setData({ user }); })
      .catch(() => {}); // 401 已由 api.js 统一跳登录
  },
  async logout() {
    if (!await fb.confirm('确定退出登录吗？', '退出')) return;
    api.logout();
  },
});
