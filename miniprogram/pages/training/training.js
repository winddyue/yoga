const api = require('../../api.js');
const fb = require('../../utils/feedback.js');

Page({
  data: { plans: [], diets: [], clientId: null, loading: true, loadErr: '', needLogin: false },
  onShow() { this.load(); },
  async load() {
    this.setData({ loading: true, loadErr: '', needLogin: false });
    // 登录态由全局统一解析（含静默续期）
    const user = await getApp().ensureUser();
    if (!user) {
      this.setData({ loading: false, needLogin: true });
      return;
    }
    try {
      const c = await api.get('/api/clients/mine');
      this.setData({ clientId: c.id });
      const [plans, diets] = await Promise.all([
        api.get(`/api/clients/${c.id}/plans`),
        api.get(`/api/clients/${c.id}/diets`),
      ]);
      this.setData({ plans: plans || [], diets: diets || [], loading: false });
    } catch (e) {
      if (e.message === '未登录') {
        this.setData({ loading: false, needLogin: true });
        return;
      }
      this.setData({ loading: false, loadErr: e.message });
    }
  },
  goLogin() { wx.navigateTo({ url: '/pages/auth/auth' }); },
});
