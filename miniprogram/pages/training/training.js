const api = require('../../api.js');
const { syncTheme, getTheme, currentThemeId } = require('../../utils/themes.js');
const chart = require('../../utils/chart.js');
const fb = require('../../utils/feedback.js');

Page({
  data: {
    plans: [], diets: [], clientId: null,
    charts: null, metric: 'weight', empty: false,
    loading: true, loadErr: '', needLogin: false,
  },
  onShow() { syncTheme(this); this.load(); },
  async load() {
    this.setData({ loading: true, loadErr: '', needLogin: false });
    // 登录态由全局统一解析（含静默续期）
    const user = await getApp().ensureUser();
    if (!user) {
      this.setData({ loading: false, needLogin: true });
      return;
    }
    try {
      const c = await api.get('/api/clients/mine');
      const [plans, diets] = await Promise.all([
        api.get(`/api/clients/${c.id}/plans`),
        api.get(`/api/clients/${c.id}/diets`),
      ]);
      let charts = null;
      try { charts = await api.get('/api/dashboard/me/charts'); } catch (e) {}
      const hasTrend = !!(charts && charts.trends && charts.trends.dates.length);
      this.setData({
        clientId: c.id,
        plans: plans || [], diets: diets || [], charts,
        empty: !(plans || []).length && !(diets || []).length && !hasTrend,
        loading: false,
      }, () => { setTimeout(() => this.drawTrend(), 80); });
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

  // 趋势指标切换：体重 / 体脂 / 腰围
  switchMetric(e) {
    const m = e.currentTarget.dataset.m;
    if (m === this.data.metric) return;
    this.setData({ metric: m }, () => this.drawTrend());
  },

  drawTrend() {
    const charts = this.data.charts;
    if (!charts || !charts.trends || !charts.trends.dates.length) return;
    const th = getTheme(currentThemeId());
    const m = this.data.metric;
    const color = m === 'weight' ? th.pri : (m === 'body_fat' ? '#D9A85F' : th.acc);
    chart.drawTrend(this, 'trainTrend', charts.trends, m, color);
  },
});
