const api = require('../../api.js');
Page({
  data: { s: null },
  onShow() {
    const user = getApp().globalData.user;
    const url = user && user.role === 'client' ? '/api/dashboard/me/summary'
      : user && user.role === 'owner' ? '/api/dashboard/owner/overview'
      : '/api/dashboard/coach/overview';
    api.get(url).then((s) => this.setData({ s })).catch(console.error);
  },
});
