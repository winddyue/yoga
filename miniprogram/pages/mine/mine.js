const api = require('../../api.js');
const { syncTheme } = require('../../utils/themes.js');
const fb = require('../../utils/feedback.js');

const ROLE_TEXT = { owner: '馆主', coach: '教练', client: '会员' };

Page({
  data: { user: null, roleText: '', loading: true, unread: 0 },

  onShow() { syncTheme(this); this.load(); },

  async load() {
    this.setData({ loading: true });
    // 复用全局解析结果（含静默续期），不重复发请求
    const user = await getApp().ensureUser();
    this.setData({
      user,
      roleText: user ? (ROLE_TEXT[user.role] || '') : '',
      loading: false,
    });
    if (user) {
      try {
        const r = await api.get('/api/notifications/unread-count');
        this.setData({ unread: r.unread || 0 });
      } catch (e) { /* 忽略 */ }
    }
  },

  goLogin() { wx.navigateTo({ url: '/pages/auth/auth' }); },

  // 未登录时点头部整块也进登录页；已登录则无操作
  onHeaderTap() { if (!this.data.user) this.goLogin(); },

  goCoach() { wx.navigateTo({ url: '/pages/coach/coach' }); },

  goNotices() { wx.navigateTo({ url: '/pages/notices/notices' }); },

  // 以下四项此前只有样式没有 bindtap，是纯死链接，点了没反应
  goProfile() { wx.navigateTo({ url: '/pages/profile/profile' }); },
  goRecords(e) {
    const tab = e.currentTarget.dataset.tab || 'booking';
    wx.navigateTo({ url: `/pages/records/records?tab=${tab}` });
  },
  goAbout() { wx.navigateTo({ url: '/pages/about/about' }); },
  goTheme() { wx.navigateTo({ url: '/pages/theme/theme' }); },

  goMeasure() { wx.navigateTo({ url: '/pages/measure/measure' }); },

  async logout() {
    if (!await fb.confirm('确定退出登录吗？下次进入需重新登录。', '退出')) return;
    api.logout();
    // 同时清空全局缓存，避免页面仍读到旧的登录态
    getApp().clearUser();
    this.setData({ user: null, roleText: '' });
  },
});
