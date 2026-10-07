const api = require('../../api.js');
const fb = require('../../utils/feedback.js');

const ROLE_TEXT = { owner: '馆主', coach: '教练', client: '会员' };

Page({
  data: { user: null, roleText: '', loading: true },

  onShow() { this.load(); },

  async load() {
    this.setData({ loading: true });
    // 复用全局解析结果（含静默续期），不重复发请求
    const user = await getApp().ensureUser();
    this.setData({
      user,
      roleText: user ? (ROLE_TEXT[user.role] || '') : '',
      loading: false,
    });
  },

  goLogin() { wx.navigateTo({ url: '/pages/auth/auth' }); },

  // 未登录时点头部整块也进登录页；已登录则无操作
  onHeaderTap() { if (!this.data.user) this.goLogin(); },

  goCoach() { wx.navigateTo({ url: '/pages/coach/coach' }); },

  async logout() {
    if (!await fb.confirm('确定退出登录吗？下次进入需重新登录。', '退出')) return;
    api.logout();
    // 同时清空全局缓存，避免页面仍读到旧的登录态
    getApp().clearUser();
    this.setData({ user: null, roleText: '' });
  },
});
