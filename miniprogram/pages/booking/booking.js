const api = require('../../api.js');
Page({
  data: { courses: [], mine: [] },
  onShow() { this.load(); },
  load() {
    api.get('/api/courses').then((courses) => this.setData({ courses })).catch(console.error);
    api.get('/api/bookings/mine').then((mine) => this.setData({ mine })).catch(() => {});
  },
  async book(e) {
    await api.post(`/api/courses/${e.currentTarget.dataset.id}/book`, {});
    wx.showToast({ title: '预约成功' }); this.load();
  },
  async cancel(e) {
    await api.post(`/api/courses/${e.currentTarget.dataset.id}/cancel`, {});
    wx.showToast({ title: '已取消' }); this.load();
  },
  // 扫码签到：二维码内容为签到码
  scanCheckin(e) {
    const id = e.currentTarget.dataset.id;
    wx.scanCode({
      success: (res) => {
        api.post(`/api/courses/${id}/checkin`, { code: res.result })
          .then(() => { wx.showToast({ title: '签到成功' }); this.load(); })
          .catch((err) => wx.showToast({ title: err.message, icon: 'none' }));
      },
    });
  },
});
