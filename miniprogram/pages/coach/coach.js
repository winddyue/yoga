const api = require('../../api.js');
Page({
  data: { courses: [], roster: [], cur: null },
  onShow() { api.get('/api/courses').then((courses) => this.setData({ courses })).catch(console.error); },
  async openRoster(e) {
    const id = e.currentTarget.dataset.id;
    const roster = await api.get(`/api/courses/${id}/roster`);
    this.setData({ roster, cur: id });
  },
  async checkin(e) {
    await api.post(`/api/courses/${this.data.cur}/checkin`, { client_id: e.currentTarget.dataset.cid });
    wx.showToast({ title: '已签到' }); this.openRoster({ currentTarget: { dataset: { id: this.data.cur } } });
  },
});
