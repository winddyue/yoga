// 客户列表（工作人员）：搜索 + 状态灯，点击进客户详情。
const api = require('../../api.js');
const { syncTheme } = require('../../utils/themes.js');
const fb = require('../../utils/feedback.js');

const LIGHT = { red: '🔴', yellow: '🟡', green: '🟢' };

Page({
  data: {
    theme: '', keyword: '', all: [], list: [],
    loading: true, loadErr: '', needLogin: false,
  },

  onShow() { syncTheme(this); this.load(); },

  async load() {
    this.setData({ loading: true, loadErr: '', needLogin: false });
    const user = await getApp().ensureUser();
    if (!user) {
      this.setData({ loading: false, needLogin: true });
      return;
    }
    if (user.role !== 'coach' && user.role !== 'owner') {
      fb.showError({ message: '无权限，仅工作人员可查看' });
      setTimeout(() => wx.navigateBack(), 900);
      return;
    }
    try {
      // coach/overview 自带 clients（含状态灯/出勤率），馆主看全馆、教练看名下
      const d = await fb.withFeedback(api.get('/api/dashboard/coach/overview'), { loading: '加载中…' });
      const all = (d.clients || []).map((c) => ({
        id: c.id,
        name: c.name,
        goal: c.goal || '',
        light: LIGHT[c.status] || '',
        att: Math.round((c.attendance_rate || 0) * 100),
      }));
      this.setData({ all }, () => {
        this.applyFilter();
        this.setData({ loading: false });
      });
    } catch (e) {
      const expired = e.message === '未登录';
      this.setData({ loading: false, loadErr: expired ? '' : e.message, needLogin: expired });
    }
  },

  goLogin() { wx.navigateTo({ url: '/pages/auth/auth' }); },

  onSearch(e) {
    this.setData({ keyword: e.detail.value }, () => this.applyFilter());
  },

  applyFilter() {
    const kw = (this.data.keyword || '').trim();
    const list = kw
      ? this.data.all.filter((c) => (c.name || '').indexOf(kw) >= 0)
      : this.data.all.slice();
    this.setData({ list });
  },

  goDetail(e) {
    const id = e.currentTarget.dataset.id;
    wx.navigateTo({ url: `/pages/client-detail/client-detail?id=${id}` });
  },
});
