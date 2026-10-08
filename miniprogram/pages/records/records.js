const api = require('../../api.js');
const { syncTheme } = require('../../utils/themes.js');
const { STATUS_TEXT, BOOKING_STATUSES, CHECKIN_STATUSES } = require('../../utils/status.js');

// 「我的预约」与「签到记录」共用本页，靠 tab 参数区分，避免为两个列表各写一套
const TAB_CONF = {
  booking: { title: '我的预约', statuses: BOOKING_STATUSES, empty: '暂无预约记录' },
  checkin: { title: '签到记录', statuses: CHECKIN_STATUSES, empty: '暂无签到记录' },
};

Page({
  data: {
    tab: 'booking',
    title: '我的预约',
    list: [],
    loading: true,
    loadErr: '',
    needLogin: false,
  },

  onLoad(options) {
    const tab = (options && options.tab) || 'booking';
    const conf = TAB_CONF[tab] || TAB_CONF.booking;
    this.setData({ tab, title: conf.title });
    wx.setNavigationBarTitle({ title: conf.title });
  },

  onShow() { syncTheme(this); this.load(); },

  async load() {
    this.setData({ loading: true, loadErr: '', needLogin: false });
    const user = await getApp().ensureUser();
    if (!user) {
      this.setData({ loading: false, needLogin: true, list: [] });
      return;
    }
    try {
      const rows = await api.get('/api/bookings/mine');
      const conf = TAB_CONF[this.data.tab] || TAB_CONF.booking;
      const list = (rows || [])
        .filter((b) => conf.statuses.indexOf(b.status) >= 0)
        .map((b) => Object.assign({}, b, {
          status_text: STATUS_TEXT[b.status] || b.status,
          when: (b.start_time || '').slice(5, 16), // 去掉年份，展示 MM-DD HH:MM
        }));
      this.setData({ list, loading: false });
    } catch (e) {
      if (e.message === '未登录') {
        this.setData({ loading: false, needLogin: true, list: [] });
        return;
      }
      this.setData({ loading: false, loadErr: e.message });
    }
  },

  switchTab(e) {
    const tab = e.currentTarget.dataset.tab;
    const conf = TAB_CONF[tab] || TAB_CONF.booking;
    this.setData({ tab, title: conf.title, list: [] });
    wx.setNavigationBarTitle({ title: conf.title });
    this.load();
  },

  goBooking() { wx.switchTab({ url: '/pages/booking/booking' }); },
  goLogin() { wx.navigateTo({ url: '/pages/auth/auth' }); },
});
