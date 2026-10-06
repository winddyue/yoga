const api = require('../../api.js');
const fb = require('../../utils/feedback.js');

Page({
  data: { s: null, loading: true, loadErr: '' },
  onShow() { this.load(); },
  async load() {
    this.setData({ loading: true, loadErr: '' });
    try {
      const user = getApp().globalData.user || await api.get('/api/auth/me');
      getApp().globalData.user = user;
      const url = user.role === 'client' ? '/api/dashboard/me/summary'
        : user.role === 'owner' ? '/api/dashboard/owner/overview'
        : '/api/dashboard/coach/overview';
      const s = await api.get(url);
      this.setData({ s, loading: false });
    } catch (e) {
      this.setData({ loading: false, loadErr: e.message });
    }
  },
});
