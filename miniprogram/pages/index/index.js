const api = require('../../api.js');

Page({
  data: { s: null, user: null, loading: true, loadErr: '', needLogin: false },

  onShow() { this.load(); },

  async load() {
    this.setData({ loading: true, loadErr: '', needLogin: false });
    // 等全局登录态解析完（含静默续期），避免和首页请求竞态
    const user = await getApp().ensureUser();
    if (!user) {
      this.setData({ loading: false, needLogin: true, user: null });
      return;
    }
    this.setData({ user });
    try {
      const url = user.role === 'client' ? '/api/dashboard/me/summary'
        : user.role === 'owner' ? '/api/dashboard/owner/overview'
        : '/api/dashboard/coach/overview';
      const s = await api.get(url);
      this.setData({ s, loading: false });
    } catch (e) {
      if (e.message === '未登录') {
        this.setData({ loading: false, needLogin: true, user: null });
        return;
      }
      this.setData({ loading: false, loadErr: e.message });
    }
  },

  goLogin() { wx.navigateTo({ url: '/pages/auth/auth' }); },
});
