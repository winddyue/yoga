const api = require('../../api.js');
const { syncTheme, getTheme, currentThemeId } = require('../../utils/themes.js');
const chart = require('../../utils/chart.js');
const checkinLib = require('../../utils/checkin.js');

Page({
  data: {
    s: null, user: null, loading: true, loadErr: '', needLogin: false,
    coachData: null,      // 馆主：全馆客户状态（阶段分布/管理表）
    charts: null,         // 客户：图表数据包
    metric: 'weight',     // 客户迷你趋势：weight / body_fat
    checkinDays: 0,       // 客户：本月打卡天数
    pendingDiets: 0,      // 馆主：待确认饮食数
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
        // 本月打卡天数（替代此前的"待上课程"，约课功能已暂隐）
        try {
          const cks = await api.get('/api/checkins/mine') || [];
          patch.checkinDays = new Set(cks.map((c) => c.date)).size;
        } catch (e) {}
      }
      if (user.role === 'owner') {
        // 馆主额外拿全馆客户状态灯，用于阶段分布和管理表
        try {
          const cd = await api.get('/api/dashboard/coach/overview');
          const enriched = this._enrichCoachData(cd);
          patch.coachData = enriched;
          patch.pendingDiets = enriched.pendingDiets;
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
      pendingDiets: (cd.todos && cd.todos.pending_diets) || 0,
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

  // ↓↓↓ 金刚区快捷入口（工作人员）
  goIntake() { wx.navigateTo({ url: '/pages/intake/intake' }); },
  goIntakePhoto() { wx.navigateTo({ url: '/pages/intake/intake?tab=photo' }); },
  goNewClient() { wx.navigateTo({ url: '/pages/client-form/client-form' }); },
  goClients() { wx.navigateTo({ url: '/pages/clients/clients' }); },

  // ↓↓↓ 首页数字 / 客户行下钻
  goAllClients() { wx.navigateTo({ url: '/pages/clients/clients' }); },
  goActiveClients() { wx.navigateTo({ url: '/pages/clients/clients?segment=active30' }); },
  goRiskClients() { wx.navigateTo({ url: '/pages/clients/clients?segment=risk' }); },
  // 待确认饮食在训练页处理（工作人员视图）
  goPendingDiets() { wx.switchTab({ url: '/pages/training/training' }); },
  goTraining() { wx.switchTab({ url: '/pages/training/training' }); },
  goClientDetail(e) {
    const id = e.currentTarget.dataset.id;
    if (id) wx.navigateTo({ url: `/pages/client-detail/client-detail?id=${id}` });
  },

  // 客户端金刚区「拍照打卡」：先选训练/饮食，再调起拍照上传
  async quickPhotoCheckin() {
    let r;
    try { r = await wx.showActionSheet({ itemList: ['训练打卡', '饮食打卡'] }); }
    catch (e) { return; } // 用户取消
    const kind = r.tapIndex === 0 ? 'training' : 'diet';
    await checkinLib.photo(kind);
    this.load(); // 刷新「本月打卡」数字
  },
});
