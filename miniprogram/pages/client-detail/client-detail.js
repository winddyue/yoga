// 客户详情（工作人员）：档案卡 + 评估历史 + 身体趋势图 + 快捷操作。
const api = require('../../api.js');
const { syncTheme, getTheme, currentThemeId } = require('../../utils/themes.js');
const chart = require('../../utils/chart.js');
const fb = require('../../utils/feedback.js');

// 从 custom_values 提取自定义字段显示项（排除 notes 备注键；空值跳过；
// key 为字段 id 字符串，字段被删后显示"已删除字段"，历史数据不受影响）
function pickCustoms(customValues, fieldMap) {
  const out = [];
  const cv = customValues || {};
  for (const k of Object.keys(cv)) {
    if (k === 'notes') continue;
    const v = cv[k];
    if (v === '' || v === null || v === undefined) continue;
    out.push({ name: fieldMap[String(k)] || '已删除字段', value: String(v) });
  }
  return out;
}

// 上课情况：预约/签到记录（后端并行开发中，失败则静默不显示该区）
const BOOKING_STATUS = {
  booked: '已约', waitlist: '候补', cancelled: '已取消',
  checked_in: '已签到', no_show: '爽约',
};

Page({
  data: {
    theme: '', id: null, client: null, history: [], trends: null,
    metric: 'weight', latestStatus: [], bookings: null,
    loading: true, loadErr: '', needLogin: false,
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
      // 上课情况：失败静默，该区不显示
      let bookings = null;
      try {
        const bl = await api.get(`/api/clients/${this.data.id}/bookings`);
        bookings = (bl || []).map((b) => ({
          title: b.course_title || '',
          time: b.start_time || '',
          status: BOOKING_STATUS[b.status] || b.status || '',
        }));
      } catch (e) {}
      // 自定义字段 id→name 映射（用于历史记录中显示字段名；字段被删则显示"已删除字段"）
      let fieldMap = {};
      try {
        const all = await api.get('/api/custom-fields');
        (all || []).forEach((f) => { fieldMap[String(f.id)] = f.name; });
      } catch (e) {}
      const rows = (history || []).slice().sort((a, b) => String(b.date).localeCompare(String(a.date)));
      // 最新状态：取最新一条评估，有值的指标（最多6项，两列网格）
      const latest = rows[0] || null;
      const latestStatus = [];
      if (latest) {
        const items = [
          ['体重', latest.weight_kg, 'kg', 1],
          ['体脂率', latest.body_fat_pct, '%', 1],
          ['肌肉量', latest.muscle_kg, 'kg', 1],
          ['BMI', latest.bmi, '', 1],
          ['腰围', latest.waist_cm, 'cm', 1],
          ['静息心率', latest.resting_hr, 'bpm', 0],
        ];
        for (const [label, v, unit, dec] of items) {
          if (typeof v === 'number' && v > 0) {
            const text = dec ? `${(+v).toFixed(1)}${unit}` : `${v}${unit}`;
            latestStatus.push({ label, text });
            if (latestStatus.length >= 6) break;
          }
        }
      }
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
            delta: d, customs: pickCustoms(r.custom_values, fieldMap),
          };
        }),
        trends, loading: false,
        latestStatus, bookings,
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
