const api = require('../../api.js');
const { syncTheme, getTheme, currentThemeId } = require('../../utils/themes.js');
const chart = require('../../utils/chart.js');
const delta = require('../../utils/delta.js');
const fb = require('../../utils/feedback.js');

function todayYM() {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`;
}

Page({
  data: {
    role: '', // client | staff
    plans: [], diets: [], clientId: null,
    charts: null, metric: 'weight', empty: false,
    delta: null, deltaCls: '',
    attPct: 0, attRate: 0, monthCount: 0, daysSince: null,
    summary: null,
    pendingDiets: [], dueReassess: 0,
    loading: true, loadErr: '', needLogin: false,
  },
  onShow() { syncTheme(this); this.load(); },
  async load() {
    this.setData({ loading: true, loadErr: '', needLogin: false, role: '' });
    // 登录态由全局统一解析（含静默续期）
    const user = await getApp().ensureUser();
    if (!user) {
      this.setData({ loading: false, needLogin: true });
      return;
    }
    // 工作人员走训练管理视图，不再调仅客户可用的 /api/clients/mine
    if (user.role === 'coach' || user.role === 'owner') {
      await this.loadStaff();
      return;
    }
    await this.loadClient();
  },

  // 工作人员视图：待确认饮食 + 需复测提醒 + 客户管理入口
  async loadStaff() {
    try {
      const [diets, overview] = await Promise.all([
        api.get('/api/diets/pending').catch(() => []),
        api.get('/api/dashboard/coach/overview').catch(() => null),
      ]);
      this.setData({
        role: 'staff',
        pendingDiets: diets || [],
        dueReassess: (overview && overview.todos && overview.todos.due_reassess) || 0,
        loading: false,
      });
    } catch (e) {
      const expired = e.message === '未登录';
      this.setData({ loading: false, loadErr: expired ? '' : e.message, needLogin: expired });
    }
  },

  // 客户视图：健康仪表盘 + 趋势 + 计划 + 饮食
  async loadClient() {
    try {
      const c = await api.get('/api/clients/mine');
      const [plans, diets] = await Promise.all([
        api.get(`/api/clients/${c.id}/plans`),
        api.get(`/api/clients/${c.id}/diets`),
      ]);
      let charts = null;
      try { charts = await api.get('/api/dashboard/me/charts'); } catch (e) {}
      // 本月总结：失败静默不显示
      let summary = null;
      try { summary = await api.get('/api/dashboard/me/monthly'); } catch (e) {}
      const hasTrend = !!(charts && charts.trends && charts.trends.dates.length);
      // 健康仪表盘数据：出勤率 / 本月体测次数 / 距上次评估天数
      const attRate = c.attendance_rate || 0;
      const dates = (charts && charts.trends && charts.trends.dates) || [];
      const ym = todayYM();
      const monthCount = dates.filter((d) => String(d).slice(0, 7) === ym).length;
      let daysSince = null;
      if (dates.length) {
        const last = new Date(String(dates[dates.length - 1]) + 'T00:00:00');
        const now = new Date();
        now.setHours(0, 0, 0, 0);
        daysSince = Math.max(0, Math.round((now - last) / 86400000));
      }
      this.setData({
        role: 'client',
        clientId: c.id,
        plans: plans || [], diets: diets || [], charts,
        attRate, attPct: Math.round(attRate * 100),
        monthCount, daysSince, summary,
        empty: !(plans || []).length && !(diets || []).length && !hasTrend,
        loading: false,
      }, () => {
        this.computeDelta();
        setTimeout(() => { this.drawTrend(); this.drawDash(); }, 80);
      });
    } catch (e) {
      if (e.message === '未登录') {
        this.setData({ loading: false, needLogin: true });
        return;
      }
      this.setData({ loading: false, loadErr: e.message });
    }
  },
  goLogin() { wx.navigateTo({ url: '/pages/auth/auth' }); },
  goMeasure() { wx.navigateTo({ url: '/pages/measure/measure' }); },
  goClients() { wx.navigateTo({ url: '/pages/clients/clients' }); },

  // 工作人员：一键确认饮食（逻辑同教练工作台）
  async confirmDiet(e) {
    const id = e.currentTarget.dataset.id;
    const ok = await fb.confirm('确认该饮食方案？确认后将通知客户。', '确认');
    if (!ok) return;
    try {
      await fb.withFeedback(api.post(`/api/diets/${id}/confirm`, {}), { loading: '确认中…' });
      fb.showSuccess('已确认');
      this.loadStaff();
    } catch (err) { /* 已提示 */ }
  },

  // 趋势指标切换：体重 / 体脂 / 腰围
  switchMetric(e) {
    const m = e.currentTarget.dataset.m;
    if (m === this.data.metric) return;
    this.setData({ metric: m }, () => { this.computeDelta(); this.drawTrend(); });
  },

  // 较上次对比 chip（当前 tab 指标）
  computeDelta() {
    const t = this.data.charts && this.data.charts.trends;
    const d = delta.lastDelta(t, this.data.metric);
    this.setData({ delta: d, deltaCls: delta.deltaCls(d) });
  },

  drawTrend() {
    const charts = this.data.charts;
    if (!charts || !charts.trends || !charts.trends.dates.length) return;
    const th = getTheme(currentThemeId());
    const m = this.data.metric;
    const color = m === 'weight' ? th.pri : (m === 'body_fat' ? '#D9A85F' : th.acc);
    chart.drawTrend(this, 'trainTrend', charts.trends, m, color);
  },

  // 健康仪表盘：出勤率圆环
  drawDash() {
    chart.drawRing(this, 'trainRing', this.data.attRate || 0);
  },
});
