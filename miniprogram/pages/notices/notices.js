// 通知列表：下拉刷新，点击标已读
const api = require('../../api.js');
const { syncTheme } = require('../../utils/themes.js');

Page({
  data: { list: [], loading: true, loadErr: '' },

  onShow() { syncTheme(this); this.load(); },

  async load() {
    this.setData({ loading: true, loadErr: '' });
    try {
      const list = await api.get('/api/notifications?limit=30');
      this.setData({ list: list || [], loading: false });
    } catch (e) {
      this.setData({ loading: false, loadErr: e.message });
    }
    wx.stopPullDownRefresh && wx.stopPullDownRefresh();
  },

  onPullDownRefresh() { this.load(); },

  async markRead(e) {
    const id = e.currentTarget.dataset.id;
    try { await api.post(`/api/notifications/${id}/read`, {}); } catch (err) {}
    this.setData({
      list: this.data.list.map((n) => (n.id === id ? { ...n, is_read: true } : n)),
    });
  },

  async markAll() {
    try { await api.post('/api/notifications/read-all', {}); } catch (err) {}
    this.setData({ list: this.data.list.map((n) => ({ ...n, is_read: true })) });
    wx.showToast({ title: '已全部标为已读', icon: 'none' });
  },
});
