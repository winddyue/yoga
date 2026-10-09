// 客户列表（工作人员）：搜索 + 状态灯，点击进客户详情。
const api = require('../../api.js');
const { syncTheme } = require('../../utils/themes.js');
const fb = require('../../utils/feedback.js');

const LIGHT = { red: '🔴', yellow: '🟡', green: '🟢' };
// 分层口径：new=30天内新建；active30=近30天有预约；其余按状态灯
// 注意 status=green 的含义是"状态正常"，不是"活跃"，故不再叫"活跃客户"，
// 避免与首页「近30天活跃」两个"活跃"打架。
const SEG_NAMES = {
  new: '新客', active30: '近30天活跃',
  active: '状态正常', dormant: '待跟进', risk: '需关注',
};

Page({
  data: {
    theme: '', keyword: '', all: [], list: [],
    loading: true, loadErr: '', needLogin: false,
    segment: '', segTitle: '',
  },

  onLoad(options) {
    this.setData({ segment: (options && options.segment) || '' });
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
        status: c.status || '',
        recent: !!c.recent_active,
        created_at: c.created_at || '',
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

  // 分层过滤：new=30天内新建；active30=近30天有预约；active/dormant/risk=状态灯
  matchSegment(c) {
    const seg = this.data.segment;
    if (!seg) return true;
    if (seg === 'new') {
      if (!c.created_at) return true; // 无字段时不过滤
      const days = (Date.now() - new Date(c.created_at + 'T00:00:00').getTime()) / 86400000;
      return days <= 30;
    }
    if (seg === 'active30') return c.recent === true;
    if (seg === 'active') return c.status === 'green';
    if (seg === 'dormant') return c.status === 'yellow';
    if (seg === 'risk') return c.status === 'red';
    return true;
  },

  applyFilter() {
    const kw = (this.data.keyword || '').trim();
    const list = this.data.all
      .filter((c) => this.matchSegment(c))
      .filter((c) => !kw || (c.name || '').indexOf(kw) >= 0);
    const segName = SEG_NAMES[this.data.segment];
    this.setData({
      list,
      segTitle: segName ? `${segName}（${list.length}）` : '',
    });
  },

  goDetail(e) {
    const id = e.currentTarget.dataset.id;
    wx.navigateTo({ url: `/pages/client-detail/client-detail?id=${id}` });
  },

  goNewClient() { wx.navigateTo({ url: '/pages/client-form/client-form' }); },
});
