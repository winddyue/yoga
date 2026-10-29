const api = require('../../api.js');
const { syncTheme, getTheme, currentThemeId } = require('../../utils/themes.js');
const chart = require('../../utils/chart.js');

Page({
  data: {
    s: null, user: null, loading: true, loadErr: '', needLogin: false,
    coachData: null,      // 馆主：全馆客户状态（阶段分布/管理表）
    charts: null,         // 客户：图表数据包
    metric: 'weight',     // 客户迷你趋势：weight / body_fat
  },

  onShow() { syncTheme(this); this.load(); },

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
      const patch = { s, loading: false };
      if (user.role === 'client') {
        s.attendancePct = Math.round((s.attendance_rate || 0) * 100);
        try { patch.charts = await api.get('/api/dashboard/me/charts'); } catch (e) {}
      }
      if (user.role === 'owner') {
        // 馆主额外拿全馆客户状态灯，用于阶段分布和管理表
        try {
          const cd = await api.get('/api/dashboard/coach/overview');
          patch.coachData = this._enrichCoachData(cd);
        } catch (e) {}
      }
      if (user.role === 'coach' && s.clients) {
        // 待办按优先级：红灯（流失风险/超期未复测）优先，其次黄灯
        const order = { red: 0, yellow: 1, green: 2 };
        s.clients = s.clients.map((c) => this._enrichClient(c))
          .sort((a, b) => (order[a.status] ?? 9) - (order[b.status] ?? 9));
      }
      this.setData(patch, () => {
        if (user.role === 'client' && this.data.s) {
          // canvas 需等 wxml 渲染完再画
          setTimeout(() => { this.drawTrend(); this.drawRing(); }, 80);
        }
      });
    } catch (e) {
      if (e.message === '未登录') {
        this.setData({ loading: false, needLogin: true, user: null });
        return;
      }
      this.setData({ loading: false, loadErr: e.message });
    }
  },

  // 客户行展示字段：出勤百分比、距上次评估文案
  _enrichClient(c) {
    return Object.assign({}, c, {
      attendancePct: Math.round((c.attendance_rate || 0) * 100),
      daysText: c.days_since_assessment == null ? '尚未评估'
        : `距上次评估${c.days_since_assessment}天`,
    });
  },

  // 馆主数据：红灯在前排序 + 阶段计数 + 堆叠条百分比
  _enrichCoachData(cd) {
    const order = { red: 0, yellow: 1, green: 2 };
    const clients = (cd.clients || []).map((c) => this._enrichClient(c))
      .sort((a, b) => (order[a.status] ?? 9) - (order[b.status] ?? 9));
    const cnt = { red: 0, yellow: 0, green: 0 };
    clients.forEach((c) => { if (cnt[c.status] !== undefined) cnt[c.status] += 1; });
    const total = clients.length || 1;
    return Object.assign({}, cd, {
      clients,
      redN: cnt.red, yellowN: cnt.yellow, greenN: cnt.green,
      redPct: (cnt.red / total) * 100,
      yellowPct: (cnt.yellow / total) * 100,
      greenPct: (cnt.green / total) * 100,
    });
  },

  goLogin() { wx.navigateTo({ url: '/pages/auth/auth' }); },

  // 趋势指标切换：体重 / 体脂
  switchMetric(e) {
    const m = e.currentTarget.dataset.m;
    if (m === this.data.metric) return;
    this.setData({ metric: m }, () => this.drawTrend());
  },

  // 客户首页迷你趋势图：逻辑在 utils/chart.js，index 只做指标配色
  drawTrend() {
    const charts = this.data.charts;
    if (!charts || !charts.trends) return;
    const th = getTheme(currentThemeId());
    const color = this.data.metric === 'weight' ? th.pri : '#D9A85F';
    chart.drawTrend(this, 'trendCanvas', charts.trends, this.data.metric, color);
  },

  // 出勤目标圆环：当前出勤率 vs 100% 目标（行业共识做法，一眼看到差距）
  drawRing() {
    const rate = (this.data.s && this.data.s.attendance_rate) || 0;
    chart.drawRing(this, 'goalRing', rate);
  },

  goMeasure() { wx.navigateTo({ url: '/pages/measure/measure' }); },

  // 会员分层下钻：跳客户列表并按分层过滤
  goSegment(e) {
    const seg = e.currentTarget.dataset.seg;
    wx.navigateTo({ url: `/pages/clients/clients?segment=${seg}` });
  },
});
