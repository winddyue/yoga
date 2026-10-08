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
    // 身体成分
    height: '', weight: '', bodyFat: '', muscle: '', visceral: '', bmiText: '',
    // 围度
    chest: '', waist: '', hip: '', arm: '', thigh: '',
    // 健康指标
    restingHr: '', bloodPressure: '', injuries: '', notes: '',
    // 自定义字段（target=assessment，馆主维护）：[{id, name, field_type, val}]
    cfFields: [],
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
      const patch = { clientId: c.id, needConsent: !ok, loading: false };
      // 身高从客户档案预填（仅用于当场算 BMI，不回写）
      if (c.height_cm && c.height_cm > 0) patch.height = String(c.height_cm);
      // 自定义字段（评估类）
      try {
        const all = await api.get('/api/custom-fields');
        patch.cfFields = (all || []).filter((f) => f.target === 'assessment')
          .map((f) => ({ id: f.id, name: f.name, field_type: f.field_type, val: '' }));
      } catch (e) {}
      this.setData(patch, () => this._calcBmi());
    } catch (e) {
      this.setData({ loading: false, loadErr: e.message === '未登录' ? '' : e.message, needLogin: e.message === '未登录' });
    }
  },

  goLogin() { wx.navigateTo({ url: '/pages/auth/auth' }); },

  onDateChange(e) { this.setData({ date: e.detail.value }); },

  onInput(e) {
    const k = e.currentTarget.dataset.k;
    this.setData({ [k]: e.detail.value }, () => {
      if (k === 'weight' || k === 'height') this._calcBmi();
    });
  },

  // 自定义字段输入（按下标更新，避免动态 key 绑定问题）
  onCfInput(e) {
    const i = Number(e.currentTarget.dataset.i);
    this.setData({ [`cfFields[${i}].val`]: e.detail.value });
  },

  // BMI = 体重kg / (身高m)^2，保留1位；身高或体重缺失时不显示
  _calcBmi() {
    const w = this._num(this.data.weight);
    const h = this._num(this.data.height);
    let t = '';
    if (!isNaN(w) && w > 0 && !isNaN(h) && h > 0) {
      t = (w / Math.pow(h / 100, 2)).toFixed(1);
    }
    this.setData({ bmiText: t });
  },

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
    // 其余数字项：填了就必须有效；必填只有体重
    for (const [k, label] of [['height', '身高'], ['bodyFat', '体脂率'], ['muscle', '肌肉量'],
        ['visceral', '内脏脂肪等级'], ['chest', '胸围'], ['waist', '腰围'], ['hip', '臀围'],
        ['arm', '上臂围'], ['thigh', '大腿围'], ['restingHr', '静息心率']]) {
      const raw = this.data[k];
      if (raw !== '' && raw !== undefined && raw !== null) {
        const n = this._num(raw);
        if (isNaN(n) || n < 0) {
          wx.showToast({ title: `${label}请填写有效数字`, icon: 'none' });
          return;
        }
      }
    }
    // 自定义字段：数字型填了必须有效
    for (const f of this.data.cfFields) {
      if (f.field_type === 'number' && f.val !== '' && f.val !== undefined && f.val !== null) {
        const n = this._num(f.val);
        if (isNaN(n) || n < 0) {
          wx.showToast({ title: `${f.name}请填写有效数字`, icon: 'none' });
          return;
        }
      }
    }
    if (this.data.needConsent) {
      wx.showToast({ title: '请先完成上方的授权', icon: 'none' });
      return;
    }
    this.setData({ submitting: true });
    try {
      const rh = parseInt(this._num(this.data.restingHr), 10);
      const body = {
        date: this.data.date,
        weight_kg: w,
        body_fat_pct: this._num(this.data.bodyFat),
        muscle_kg: this._num(this.data.muscle),
        bmi: this.data.bmiText ? parseFloat(this.data.bmiText) : 0,
        visceral_fat: this._num(this.data.visceral),
        chest_cm: this._num(this.data.chest),
        waist_cm: this._num(this.data.waist),
        hip_cm: this._num(this.data.hip),
        arm_cm: this._num(this.data.arm),
        thigh_cm: this._num(this.data.thigh),
        resting_hr: isNaN(rh) ? 0 : rh,
        blood_pressure: this.data.bloodPressure || '',
        injuries: this.data.injuries || '',
      };
      if (this.data.notes) body.custom_values = { notes: this.data.notes };
      // 自定义字段并入 custom_values（key 为字段 id 字符串；notes 键保留给备注）
      const cv = body.custom_values || {};
      for (const f of this.data.cfFields) {
        if (f.val !== '' && f.val !== undefined && f.val !== null) {
          cv[String(f.id)] = f.field_type === 'number' ? this._num(f.val) : f.val;
        }
      }
      if (Object.keys(cv).length) body.custom_values = cv;
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

  // 再记一条：重置表单（保留身高预填）
  resetForm() {
    const cfFields = (this.data.cfFields || []).map((f) => ({ ...f, val: '' }));
    this.setData({
      date: todayStr(), weight: '', bodyFat: '', muscle: '', visceral: '', bmiText: '',
      chest: '', waist: '', hip: '', arm: '', thigh: '',
      restingHr: '', bloodPressure: '', injuries: '', notes: '',
      cfFields,
      done: false, doneRows: [], firstTime: false,
    }, () => this._calcBmi());
  },
});
