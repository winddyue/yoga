// 客户详情（工作人员）：档案卡 + 评估历史 + 身体趋势图 + 快捷操作。
const api = require('../../api.js');
const { syncTheme, getTheme, currentThemeId } = require('../../utils/themes.js');
const chart = require('../../utils/chart.js');
const fb = require('../../utils/feedback.js');

Page({
  data: {
    theme: '', id: null, client: null, history: [], trends: null,
    metric: 'weight', loading: true, loadErr: '', needLogin: false,
  },

  onLoad(options) {
    this.setData({ id: options.id ? Number(options.id) : null });
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
    if (!this.data.id) {
      this.setData({ loading: false, loadErr: '缺少客户 id' });
      return;
    }
    try {
      const [client, history] = await fb.withFeedback(Promise.all([
        api.get(`/api/clients/${this.data.id}`),
        api.get(`/api/clients/${this.data.id}/assessments`),
      ]), { loading: '加载中…' });
      let trends = null;
      try { trends = await api.get(`/api/clients/${this.data.id}/trends`); } catch (e) {}
      const rows = (history || []).slice().sort((a, b) => String(b.date).localeCompare(String(a.date)));
      this.setData({
        client: {
          name: client.name, gender: client.gender || '', age: client.age || '',
          goal: client.goal || '', phone: client.phone || '',
          att: Math.round((client.attendance_rate || 0) * 100),
        },
        history: rows.map((r, i) => {
          // 较上条（体重维度）：rows 按日期倒序，最旧的一条不显示
          let d = null;
          if (i < rows.length - 1) {
            const cur = r.weight_kg, prev = rows[i + 1].weight_kg;
            if (typeof cur === 'number' && cur > 0 && typeof prev === 'number' && prev > 0) {
              const diff = +(cur - prev).toFixed(1);
              d = {
                text: `${diff > 0 ? '+' : ''}${diff.toFixed(1)}kg`,
                cls: diff < 0 ? 'good' : (diff > 0 ? 'bad' : 'flat'),
              };
            }
          }
          return {
            date: r.date, weight: r.weight_kg || '-', bodyFat: r.body_fat_pct || '-',
            delta: d,
          };
        }),
        trends, loading: false,
      }, () => { setTimeout(() => this.drawTrend(), 80); });
    } catch (e) {
      const expired = e.message === '未登录';
      this.setData({ loading: false, loadErr: expired ? '' : e.message, needLogin: expired });
    }
  },

  goLogin() { wx.navigateTo({ url: '/pages/auth/auth' }); },

  goAssess() { wx.navigateTo({ url: `/pages/assess/assess?clientId=${this.data.id}` }); },
  goPlans() { wx.navigateTo({ url: `/pages/plans/plans?clientId=${this.data.id}` }); },
  goDiets() { wx.navigateTo({ url: `/pages/diets/diets?clientId=${this.data.id}` }); },

  // 趋势指标切换：体重 / 体脂 / 腰围
  switchMetric(e) {
    const m = e.currentTarget.dataset.m;
    if (m === this.data.metric) return;
    this.setData({ metric: m }, () => this.drawTrend());
  },

  drawTrend() {
    const t = this.data.trends;
    if (!t || !t.dates || !t.dates.length) return;
    const th = getTheme(currentThemeId());
    const m = this.data.metric;
    const color = m === 'weight' ? th.pri : (m === 'body_fat' ? '#D9A85F' : th.acc);
    chart.drawTrend(this, 'detailTrend', t, m, color);
  },
});
