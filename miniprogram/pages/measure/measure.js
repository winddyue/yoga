// 体测记录：客户自助录入体重/体脂/围度。录入前需完成敏感信息单独授权（合规）。
const api = require('../../api.js');
const { syncTheme } = require('../../utils/themes.js');
const delta = require('../../utils/delta.js');
const fb = require('../../utils/feedback.js');

function todayStr() {
  const d = new Date();
  const m = String(d.getMonth() + 1).padStart(2, '0');
  const day = String(d.getDate()).padStart(2, '0');
  return `${d.getFullYear()}-${m}-${day}`;
}

Page({
  data: {
    theme: '', date: todayStr(),
    weight: '', bodyFat: '', waist: '', hip: '', notes: '',
    clientId: null, needLogin: false, loading: true, loadErr: '',
    needConsent: false, agreeing: false, submitting: false,
    done: false, doneRows: [], firstTime: false,
  },

  onShow() { syncTheme(this); this.init(); },

  async init() {
    const user = await getApp().ensureUser();
    if (!user) {
      this.setData({ loading: false, needLogin: true });
      return;
    }
    try {
      const c = await api.get('/api/clients/mine');
      let consents = [];
      try { consents = await api.get('/api/consents/mine'); } catch (e) {}
      const ok = (consents || []).some((x) => x.consent_type === 'sensitive_info');
      this.setData({ clientId: c.id, needConsent: !ok, loading: false });
    } catch (e) {
      this.setData({ loading: false, loadErr: e.message === '未登录' ? '' : e.message, needLogin: e.message === '未登录' });
    }
  },

  goLogin() { wx.navigateTo({ url: '/pages/auth/auth' }); },

  onDateChange(e) { this.setData({ date: e.detail.value }); },

  onInput(e) { this.setData({ [e.currentTarget.dataset.k]: e.detail.value }); },

  // 单独授权：敏感信息采集同意
  async agreeConsent() {
    if (this.data.agreeing || !this.data.clientId) return;
    this.setData({ agreeing: true });
    try {
      await api.post('/api/consents', {
        client_id: this.data.clientId,
        consent_type: 'sensitive_info',
        version: 'v1',
      });
      this.setData({ needConsent: false });
      fb.showSuccess('已授权');
    } catch (e) {
      fb.showError(e, '授权失败');
    } finally {
      this.setData({ agreeing: false });
    }
  },

  _num(v) {
    if (v === '' || v === undefined || v === null) return 0;
    const n = parseFloat(v);
    return isNaN(n) ? NaN : n;
  },

  async submit() {
    if (this.data.submitting) return;
    const w = this._num(this.data.weight);
    if (isNaN(w) || w <= 0) {
      wx.showToast({ title: '请填写有效的体重', icon: 'none' });
      return;
    }
    for (const [k, label] of [['bodyFat', '体脂率'], ['waist', '腰围'], ['hip', '臀围']]) {
      const n = this._num(this.data[k]);
      if (isNaN(n) || n < 0) {
        wx.showToast({ title: `${label}请填写有效数字`, icon: 'none' });
        return;
      }
    }
    if (this.data.needConsent) {
      wx.showToast({ title: '请先完成上方的授权', icon: 'none' });
      return;
    }
    this.setData({ submitting: true });
    try {
      const body = {
        date: this.data.date,
        weight_kg: w,
        body_fat_pct: this._num(this.data.bodyFat),
        waist_cm: this._num(this.data.waist),
        hip_cm: this._num(this.data.hip),
      };
      if (this.data.notes) body.custom_values = { notes: this.data.notes };
      await api.post(`/api/clients/${this.data.clientId}/assessments`, body);
      // 提交成功：重新拉趋势（含本次新记录），页面内显示"本次 vs 上次"对比卡
      let trends = null;
      try {
        const c2 = await api.get('/api/dashboard/me/charts');
        trends = c2 && c2.trends;
      } catch (e) {}
      const dates = (trends && trends.dates) || [];
      const firstTime = dates.length <= 1;
      const rows = [{ label: '体重', cur: `${w}kg`, d: delta.lastDelta(trends, 'weight') }];
      const bf = this.data.bodyFat === '' ? NaN : this._num(this.data.bodyFat);
      if (!isNaN(bf) && bf > 0) {
        rows.push({ label: '体脂率', cur: `${bf}%`, d: delta.lastDelta(trends, 'body_fat') });
      }
      const wst = this.data.waist === '' ? NaN : this._num(this.data.waist);
      if (!isNaN(wst) && wst > 0) {
        rows.push({ label: '腰围', cur: `${wst}cm`, d: delta.lastDelta(trends, 'waist') });
      }
      rows.forEach((r) => { r.cls = delta.deltaCls(r.d); });
      this.setData({ done: true, doneRows: rows, firstTime, submitting: false });
    } catch (e) {
      if (e.message && e.message.indexOf('单独授权') >= 0) {
        this.setData({ needConsent: true });
        wx.showToast({ title: '请先完成授权', icon: 'none' });
      } else {
        fb.showError(e, '保存失败');
      }
    } finally {
      this.setData({ submitting: false });
    }
  },

  // 对比卡按钮：去训练页看趋势（tab 页用 switchTab）
  goTraining() { wx.switchTab({ url: '/pages/training/training' }); },

  // 再记一条：重置表单
  resetForm() {
    this.setData({
      date: todayStr(), weight: '', bodyFat: '', waist: '', hip: '', notes: '',
      done: false, doneRows: [], firstTime: false,
    });
  },
});
