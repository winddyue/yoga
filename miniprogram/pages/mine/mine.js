const api = require('../../api.js');
const fb = require('../../utils/feedback.js');

const ROLE_TEXT = { owner: '馆主', coach: '教练', client: '会员' };

Page({
  data: { user: null, roleText: '', loading: true },

  onShow() { this.load(); },

  async load() {
    this.setData({ loading: true });
    try {
      const user = getApp().globalData.user || await api.get('/api/auth/me');
      getApp().globalData.user = user;
      this.setData({ user, roleText: ROLE_TEXT[user.role] || '', loading: false });
    } catch (e) {
      // 未登录：正常的游客态，展示"您好，请登录"
      this.setData({ user: null, loading: false });
    }
  },

  goLogin() { wx.navigateTo({ url: '/pages/auth/auth' }); },

  // 未登录时点头部整块也进登录页；已登录则无操作
  onHeaderTap() { if (!this.data.user) this.goLogin(); },

  goCoach() { wx.navigateTo({ url: '/pages/coach/coach' }); },

  async logout() {
    if (!await fb.confirm('确定退出登录吗？', '退出')) return;
    api.logout();
    this.setData({ user: null });
  },
});
